import pandas as pd
import math
import os

class BaseRateParser:
    """
    FedEx 基础运费表(Base Rates)解析器
    读取标准化的Excel模板，转换为 Pandas DataFrame 以供极速查询
    """
    
    def __init__(self, file_path):
        self.file_path = file_path
        self.rates_df = None
        
    def parse(self, sheet_name=0):
        """
        解析 Excel 运费矩阵模板
        - 默认跳过前置的无关行 (例如第一行是说明文字)
        - 将 'Zone/Lbs' (重量列) 设为 Index
        - 将 'X区' 的列名清洗为纯数字 'X'，方便后续用整数查询
        """
        print(f"开始解析基础运费表: {os.path.basename(self.file_path)}")
        try:
            # 读取 Excel，假设表头在第2行(index 1)
            # 通过前面的探针我们看到，row 1 (index 1) 是真正的表头：Zone/Lbs, 2区, 3区...
            df = pd.read_excel(self.file_path, sheet_name=sheet_name, header=1)
            
            # 清洗列名：重命名第一列为 'Weight'
            df.rename(columns={df.columns[0]: 'Weight'}, inplace=True)
            
            # 清理包含 NaN 的行（可能是底部的空行或备注）
            df = df.dropna(subset=['Weight'])
            
            # 将重量转为整数 (假设目前只处理 1-150 lbs)
            # 注意：对于联邦的超过150磅（Freight级别）或者 1磅以下的（比如SmartPost），可能需要特殊处理
            # 暂时我们将重量强制转为 float 然后转 int（容错处理）
            df['Weight'] = pd.to_numeric(df['Weight'], errors='coerce')
            df = df.dropna(subset=['Weight'])
            df['Weight'] = df['Weight'].astype(int)
            
            # 将重量设为索引 (Index)，方便直接通过 df.loc[weight, zone] 查价
            df.set_index('Weight', inplace=True)
            
            # 清洗分区列名：将 "2区", "3区" 等替换为整数 2, 3
            # 方便引擎传入纯数字 Zone 进行查询
            new_columns = {}
            for col in df.columns:
                # 提取列名中的数字
                import re
                match = re.search(r'\d+', str(col))
                if match:
                    new_columns[col] = int(match.group())
            
            df.rename(columns=new_columns, inplace=True)
            
            # 清理那些没有被成功重命名为数字的列 (如 "Unnamed: X")
            # 保留列名是整数的列
            cols_to_keep = [col for col in df.columns if isinstance(col, int)]
            df = df[cols_to_keep]
            
            self.rates_df = df
            print("  -> 基础运费矩阵加载成功！")
            print(f"  -> 支持重量范围: {self.rates_df.index.min()} lbs - {self.rates_df.index.max()} lbs")
            print(f"  -> 支持 Zone 范围: {list(self.rates_df.columns)}")
            
            return True
            
        except Exception as e:
            print(f"解析基础运费表发生错误: {e}")
            return False

    def get_base_rate(self, actual_weight, length, width, height, zone, dim_divisor=250):
        """
        查询基础运费 (公布价)
        :param actual_weight: 实际重量 (lbs)
        :param length: 长 (inch)
        :param width: 宽 (inch)
        :param height: 高 (inch)
        :param zone: 分区 (int 或 str)
        :param dim_divisor: 抛重系数 (默认250)
        :return: 对应的基础运费 (float), 最终计费重量 (int)
        """
        if self.rates_df is None:
            raise ValueError("费率矩阵未加载，请先运行 parse() 方法。")
            
        # 1. 计算体积重 (DIM Weight)
        dim_weight = (length * width * height) / dim_divisor
        
        # 2. 确定计费重量 (Chargeable Weight): 取实际重量和体积重的较大值
        chargeable_weight = max(actual_weight, dim_weight)
        
        # 3. 重量向上取整处理 (FedEx 计费规则：1.1 lbs 算 2 lbs)
        billable_weight = math.ceil(float(chargeable_weight))
        if billable_weight == 0:
            billable_weight = 1 # 最小计费重量 1 lbs
            
        # 4. Zone 格式化
        zone = int(str(zone).replace('区', '').strip())
        
        # 5. 越界检查 (如超过最大重量)
        max_weight = self.rates_df.index.max()
        if billable_weight > max_weight:
            print(f"警告: 计费重量 {billable_weight} lbs 超出价格表上限 {max_weight} lbs。")
            return None, billable_weight
            
        # 6. 查表获取价格
        try:
            rate = self.rates_df.loc[billable_weight, zone]
            return float(rate), billable_weight
        except KeyError:
            print(f"未找到对应计费重量({billable_weight} lbs)或分区({zone})的价格。")
            return None, billable_weight

if __name__ == "__main__":
    # 测试代码
    # 改为读取用户最新上传的折后报价单
    file_path = '/Users/qiankun/Desktop/星商/自动报价系统/星商FedEx2026最新折后报价单.xlsx'
    
    parser = BaseRateParser(file_path)
    if parser.parse():
        print("\n--- 查价测试 (加入体积重逻辑) ---")
        
        # 测试 1: 实际重量大于体积重 (实重 10 lbs, 尺寸 10x10x10, 抛重系数 250)
        # 10*10*10/250 = 4 lbs. 取实重 10 lbs.
        price_1, b_weight_1 = parser.get_base_rate(actual_weight=10, length=10, width=10, height=10, zone=4, dim_divisor=250)
        print(f"[实重计费] 实重10, 尺寸10x10x10 -> 计费重量: {b_weight_1} lbs, Zone 4 的基础运费: ${price_1}")
        
        # 测试 2: 体积重大于实际重量 (实重 5 lbs, 尺寸 20x20x20, 抛重系数 250)
        # 20*20*20/250 = 32 lbs. 取体积重 32 lbs.
        price_2, b_weight_2 = parser.get_base_rate(actual_weight=5, length=20, width=20, height=20, zone=8, dim_divisor=250)
        print(f"[体积重计费] 实重5, 尺寸20x20x20 -> 计费重量: {b_weight_2} lbs, Zone 8 的基础运费: ${price_2}")
