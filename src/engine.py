import json
import os
import math
import sys

# 添加当前目录到 sys.path 以支持直接运行
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_parsers.rate_parser import BaseRateParser
from data_parsers.das_parser import DASParser

class PricingEngine:
    """
    核心计费引擎
    负责统筹基础运费、附加费用、燃油费及返点的计算逻辑。
    """
    def __init__(self, rate_file, das_file, rules_file):
        # 1. 初始化并加载基础运费表
        self.rate_parser = BaseRateParser(rate_file)
        if not self.rate_parser.parse():
            raise Exception("基础运费表加载失败！")
            
        # 2. 初始化并加载 DAS 偏远邮编库
        self.das_parser = DASParser(das_file)
        # 这里为了简化，假设 das_file 已经是解析好的 json。如果传的是 excel，需要先 parse
        if das_file.endswith('.json'):
            with open(das_file, 'r', encoding='utf-8') as f:
                self.das_parser.das_dict = json.load(f)
        else:
            self.das_parser.parse()
            
        # 3. 加载规则配置
        with open(rules_file, 'r', encoding='utf-8') as f:
            self.rules = json.load(f)
            
        self.settings = self.rules['system_settings']
        self.surcharges = self.rules['surcharge_rules']

    def evaluate_condition(self, condition_str, actual_weight, length, width, height):
        """安全地评估字符串形式的数学条件"""
        # 允许使用的变量
        local_vars = {
            'actual_weight': actual_weight,
            'length': length,
            'width': width,
            'height': height
        }
        try:
            # 使用 eval 进行计算。注意：实际生产环境中，如果 condition_str 来自不受信任的用户输入，
            # 这里需要使用更安全的表达式解析库（如 ast.literal_eval 或专门的规则引擎引擎）。
            # 在内部配置中，eval 是可控的。
            return eval(condition_str, {"__builtins__": {}}, local_vars)
        except Exception as e:
            print(f"评估条件时出错: {condition_str} -> {e}")
            return False

    def get_zone_rate(self, rates_dict, zone):
        """根据 Zone 获取对应价格，兼容 default 值和未找到的情况"""
        if "default" in rates_dict:
            return rates_dict["default"]
            
        # 尝试匹配具体的 zone (如 '2', '3')
        zone_str = str(zone)
        if zone_str in rates_dict:
            return rates_dict[zone_str]
            
        # FedEx 报价单中经常有 "7+" 代表 7及以上
        if zone >= 7 and "7" in rates_dict:
             return rates_dict["7"]
             
        return 0.0

    def calculate_quote(self, request):
        """
        计算主函数
        request 包含:
        - actual_weight: 实际重量 (lbs)
        - length, width, height: 尺寸 (inch)
        - zone: 分区 (整数)
        - zip_code: 目的邮编 (字符串)
        - is_residential: 是否住宅地址 (布尔)
        - is_irregular_packaging: 是否不规则包装 (布尔)
        - signature_option: 签名选项 (None, "Indirect", "Direct", "Adult")
        - is_address_correction: 是否修改地址 (布尔)
        """
        # --- 数据解包 ---
        aw = request.get('actual_weight', 0)
        l = request.get('length', 0)
        w = request.get('width', 0)
        h = request.get('height', 0)
        zone = request.get('zone', 2)
        zip_code = str(request.get('zip_code', ''))
        
        # 将长宽高按降序排列，确保 length 始终是最长边，width 是次长边，height 是最短边
        dims = sorted([l, w, h], reverse=True)
        length, width, height = dims[0], dims[1], dims[2]

        bill = {
            "base_rate": 0.0,
            "surcharges": {},
            "fuel_surcharge": 0.0,
            "subtotal": 0.0,
            "rebate": 0.0,
            "final_total": 0.0,
            "chargeable_weight": 0,
            "logs": []
        }

        # ==========================================
        # 1. 基础运费计算 (考虑附加费引发的最低计费重量)
        # ==========================================
        bill['logs'].append("【第一步：计费重量与基础运费计算】")
        # 默认抛重系数
        dim_divisor = self.settings.get('dim_divisor', 250)
        
        # 预先判断是否触发特殊最低计费重量 (Oversize=90, AHS_Dim=40)
        min_weight_override = 0
        
        # 检查 Oversize
        if self.evaluate_condition(self.surcharges['Oversize']['condition'], aw, length, width, height):
            min_weight_override = max(min_weight_override, self.surcharges['Oversize'].get('min_billable_weight', 90))
            bill['logs'].append(f"  -> 触发 Oversize (超大件) 规则，最低计费重量被提升至 {min_weight_override} lbs")
        # 检查 AHS_Dimension
        elif self.evaluate_condition(self.surcharges['AHS_Dimension']['condition'], aw, length, width, height):
             min_weight_override = max(min_weight_override, self.surcharges['AHS_Dimension'].get('min_billable_weight', 40))
             bill['logs'].append(f"  -> 触发 AHS_Dimension (超尺寸) 规则，最低计费重量被提升至 {min_weight_override} lbs")

        # 正常获取基础运费与基础计费重量 (这里的 base_weight 已经比较过实重和体积重了)
        dim_weight = (length * width * height) / dim_divisor
        bill['logs'].append(f"  -> 实重: {aw} lbs, 体积重 (L*W*H/{dim_divisor}): {dim_weight:.2f} lbs")
        
        base_price, base_weight = self.rate_parser.get_base_rate(
            actual_weight=aw, length=length, width=width, height=height, 
            zone=zone, dim_divisor=dim_divisor
        )
        
        if base_price is None:
            bill['logs'].append(f"  -> [错误] 无法获取基础运费 (可能超重超尺寸或缺少数据)")
            return {"error": "超出运费表限制，无法获取基础运费"}
            
        # 应用最低计费重量覆盖逻辑
        final_chargeable_weight = max(base_weight, min_weight_override)
        if final_chargeable_weight > base_weight:
            # 如果被覆盖了，需要用新的重量重新查一次价格
            base_price, _ = self.rate_parser.get_base_rate(
                actual_weight=final_chargeable_weight, length=1, width=1, height=1, # 尺寸传1避免再次算体积重
                zone=zone, dim_divisor=9999
            )
            bill['logs'].append(f"  -> [最终计费重量] 因附加费规则覆盖，实际计费重量修正为: {final_chargeable_weight} lbs")
        else:
            bill['logs'].append(f"  -> [最终计费重量] {final_chargeable_weight} lbs")

        bill['chargeable_weight'] = final_chargeable_weight
        bill['base_rate'] = base_price
        bill['logs'].append(f"  -> [查表] 获取基础运费 (Zone {zone}, {final_chargeable_weight} lbs): ${base_price:.2f}")


        # ==========================================
        # 2. 附加费计算
        # ==========================================
        bill['logs'].append("\n【第二步：各项附加费计算】")
        # 2.1 互斥类附加费计算 (Oversize vs AHS)
        # 规则：FedEx 收取最贵的那个附加费，不叠加
        mutex_fees = {}
        
        # 算 Unauthorized (天价惩罚)
        if self.evaluate_condition(self.surcharges['Unauthorized']['condition'], aw, length, width, height):
            mutex_fees['Unauthorized Package'] = self.surcharges['Unauthorized']['rates']['default']
            
        # 算 Oversize
        if self.evaluate_condition(self.surcharges['Oversize']['condition'], aw, length, width, height):
            mutex_fees['Oversize Charge'] = self.get_zone_rate(self.surcharges['Oversize']['rates'], zone)
            
        # 算 AHS - Weight
        if self.evaluate_condition(self.surcharges['AHS_Weight']['condition'], aw, length, width, height):
            mutex_fees['AHS - Weight'] = self.get_zone_rate(self.surcharges['AHS_Weight']['rates'], zone)
            
        # 算 AHS - Dimension
        if self.evaluate_condition(self.surcharges['AHS_Dimension']['condition'], aw, length, width, height):
            mutex_fees['AHS - Dimension'] = self.get_zone_rate(self.surcharges['AHS_Dimension']['rates'], zone)
            
        # 算 AHS - Packaging (由用户手动勾选传入)
        if request.get('is_irregular_packaging', False):
            mutex_fees['AHS - Packaging'] = self.get_zone_rate(self.surcharges['AHS_Packaging']['rates'], zone)

        # 选出最贵的一个记入账单
        if mutex_fees:
            max_fee_name = max(mutex_fees, key=mutex_fees.get)
            max_fee_amount = mutex_fees[max_fee_name]
            bill['surcharges'][max_fee_name] = max_fee_amount
            bill['logs'].append(f"  -> 触发互斥附加费群: {list(mutex_fees.keys())}")
            bill['logs'].append(f"  -> [最终选取最高项]: {max_fee_name} = ${max_fee_amount:.2f}")

        # 2.2 独立类附加费计算
        
        # 住宅派送费 (Residential)
        is_residential = request.get('is_residential', False)
        if is_residential:
            res_fee = self.surcharges['Residential']['rates']['default']
            bill['surcharges']['Residential Delivery'] = res_fee
            bill['logs'].append(f"  -> 触发住宅派送费: ${res_fee:.2f}")
            
        # 偏远地区附加费 (DAS)
        das_type = self.das_parser.query_zip(zip_code)
        if das_type and das_type != "非偏远地区 (None)":
            addr_type = "Residential" if is_residential else "Commercial"
            das_fee = self.surcharges['DAS']['rates'][addr_type].get(das_type, 0)
            if das_fee > 0:
                bill['surcharges'][f'DAS - {das_type} ({addr_type})'] = das_fee
                bill['logs'].append(f"  -> 触发偏远附加费 ({das_type}, {addr_type}): ${das_fee:.2f}")
                
        # 签名选项
        sig_opt = request.get('signature_option')
        if sig_opt and sig_opt in self.surcharges['Signature']['options']:
            sig_fee = self.surcharges['Signature']['options'][sig_opt]
            bill['surcharges'][f'Signature ({sig_opt})'] = sig_fee
            bill['logs'].append(f"  -> 触发签名费: ${sig_fee:.2f}")
            
        # 地址更正
        if request.get('is_address_correction', False):
            addr_fee = self.surcharges['Address_Correction']['rates']['default']
            bill['surcharges']['Address Correction'] = addr_fee
            bill['logs'].append(f"  -> 触发地址修改费: ${addr_fee:.2f}")

        # ==========================================
        # 3. 燃油附加费计算
        # ==========================================
        bill['logs'].append("\n【第三步：燃油附加费计算】")
        # 实际支付燃油费 = (折后运费 + 折后附加费总和) × FedEx公布燃油费率（25.5%）× 70%
        surcharges_total = sum(bill['surcharges'].values())
        base_for_fuel = bill['base_rate'] + surcharges_total
        
        fuel_rate = self.settings.get('fuel_surcharge_rate', 0.255)
        fuel_discount = self.settings.get('fuel_surcharge_discount', 0.70)
        
        fuel_fee = base_for_fuel * fuel_rate * fuel_discount
        bill['fuel_surcharge'] = round(fuel_fee, 2)
        bill['logs'].append(f"  -> 计算基数: 基础运费(${bill['base_rate']}) + 附加费总和(${surcharges_total}) = ${base_for_fuel:.2f}")
        bill['logs'].append(f"  -> 燃油费率: {fuel_rate*100}% (官方) * {fuel_discount*100}% (折扣)")
        bill['logs'].append(f"  -> [最终燃油附加费]: ${base_for_fuel:.2f} * {fuel_rate} * {fuel_discount} = ${fuel_fee:.2f}")

        # ==========================================
        # 4. 总计与返点计算
        # ==========================================
        bill['logs'].append("\n【第四步：总计与返点核算】")
        # 账单总额 (Subtotal) = 基础运费 + 所有附加费 + 燃油费
        subtotal = bill['base_rate'] + surcharges_total + bill['fuel_surcharge']
        bill['subtotal'] = round(subtotal, 2)
        bill['logs'].append(f"  -> 账单总额 (向FedEx支付): ${bill['subtotal']:.2f}")
        
        # 信用卡返点
        rebate_rate = self.settings.get('credit_card_rebate_rate', 0.016)
        rebate = subtotal * rebate_rate
        bill['rebate'] = round(rebate, 2)
        bill['logs'].append(f"  -> 信用卡返点计算: 账单总额 ${bill['subtotal']:.2f} * 返点率 {rebate_rate*100}% = ${bill['rebate']:.2f}")
        
        # 最终实际成本
        bill['final_total'] = round(subtotal - rebate, 2)
        bill['logs'].append(f"  -> [最终实际成本核算]: 账单总额 ${bill['subtotal']:.2f} - 返点 ${bill['rebate']:.2f} = ${bill['final_total']:.2f}")
        
        return bill

if __name__ == "__main__":
    # 简单的本地测试
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(current_dir)
    
    rate_file = os.path.join(project_dir, '星商FedEx2026最新折后报价单.xlsx')
    das_file = os.path.join(current_dir, 'data_parsers', 'das_database.json')
    rules_file = os.path.join(current_dir, 'rules.json')
    
    engine = PricingEngine(rate_file, das_file, rules_file)
    
    # 模拟一个前端传入的订单请求
    test_request = {
        "actual_weight": 55,       # 触发 AHS-Weight (>50)
        "length": 50,              # 触发 AHS-Dimension (>48)
        "width": 20,
        "height": 10,
        "zone": 5,
        "zip_code": "1002",        # DAS_ContUS 偏远地区
        "is_residential": True,    # 触发住宅费
        "is_irregular_packaging": False,
        "signature_option": "Direct", # 触发签名费
        "is_address_correction": False
    }
    
    print("\n" + "="*40)
    print(" 开始计算模拟订单报价 ".center(40, "="))
    print("="*40)
    
    result = engine.calculate_quote(test_request)
    
    for log in result['logs']:
        print("->", log)
        
    print("\n[最终账单明细]")
    print(f"计费重量: {result['chargeable_weight']} lbs")
    print(f"基础运费: ${result['base_rate']:.2f}")
    print("附加费用:")
    for k, v in result['surcharges'].items():
        print(f"  - {k}: ${v:.2f}")
    print(f"燃油附加费: ${result['fuel_surcharge']:.2f}")
    print("-" * 20)
    print(f"账单总额(支付给FedEx): ${result['subtotal']:.2f}")
    print(f"信用卡返点抵扣: -${result['rebate']:.2f}")
    print(f"最终实际物流成本: ${result['final_total']:.2f}")