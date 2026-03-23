import pandas as pd
import json
import os

class DASParser:
    """
    FedEx 偏远地区邮编(DAS)解析器
    将官方发布的多Sheet Excel转化为可供报价引擎快速查询的字典或JSON
    """
    
    def __init__(self, file_path):
        self.file_path = file_path
        self.das_dict = {} # 存储 { "1002": "DAS_ContUS", ... }
        
    def parse(self):
        """
        解析 Excel 文件并提取所有邮编及其对应的偏远类型
        """
        print(f"开始解析 DAS 邮编文件: {os.path.basename(self.file_path)}")
        try:
            xls = pd.ExcelFile(self.file_path)
            
            for sheet_name in xls.sheet_names:
                print(f"正在处理 Sheet: {sheet_name}...")
                
                # FedEx 的表格前几行通常是说明文本，列名在第 5 行 (index 4) 或第 6 行
                # 我们读取时需要跳过这些说明行。通常列名是 "Destination ZIP Codes"
                
                # 先读取一小部分来找到正确的 header 行
                df_preview = pd.read_excel(self.file_path, sheet_name=sheet_name, nrows=10)
                header_row_idx = None
                
                # 寻找包含 "Destination ZIP Codes" 或类似字眼的行
                for idx, row in df_preview.iterrows():
                    row_str = " ".join([str(val).lower() for val in row.values])
                    if "destination" in row_str or "zip" in row_str:
                        # 当前行的上一行（在原始excel中）可能是真正的header
                        # 但 pandas 默认把第一行当 header，所以需要仔细判断
                        header_row_idx = idx
                        break
                
                if header_row_idx is not None:
                    # 重新读取，跳过 header 之前的行
                    # skiprows = header_row_idx + 1 因为 df_preview 已经消耗了一行 header
                    df = pd.read_excel(self.file_path, sheet_name=sheet_name, skiprows=header_row_idx + 1)
                else:
                    # 如果没找到，尝试默认跳过前 5 行
                    df = pd.read_excel(self.file_path, sheet_name=sheet_name, skiprows=5)

                # 获取第一列的数据，清洗并存入字典
                if not df.empty:
                    # 获取第一列的列名
                    col_name = df.columns[0]
                    
                    # 提取邮编并清理 (去除 NaN，转为字符串，去除两端空格，补充前导0以确保5位)
                    zips = df[col_name].dropna().astype(str).str.strip()
                    
                    # 过滤掉非数字的表头残留物（比如 "Effective 6/2/2025" 等）
                    zips = zips[zips.str.match(r'^\d+$')]
                    
                    # 邮编标准化为5位 (如 1002 补齐为 01002，如果需要的话)
                    # FedEx 的 Excel 里东海岸的邮编经常被 Excel 自动去掉了前面的 0
                    zips = zips.apply(lambda x: x.zfill(5))
                    
                    count = 0
                    for zip_code in zips:
                        # 存入字典，Key 为邮编，Value 为偏远类型 (Sheet名)
                        self.das_dict[zip_code] = sheet_name
                        count += 1
                        
                    print(f"  -> 成功提取 {count} 个邮编，归类为 '{sheet_name}'")
                    
        except Exception as e:
            print(f"解析过程中发生错误: {e}")
            return False
            
        return True

    def save_to_json(self, output_path):
        """
        将解析后的字典保存为 JSON 文件，供报价引擎快速读取
        """
        if not self.das_dict:
            print("警告: 字典为空，请先运行 parse() 方法。")
            return
            
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.das_dict, f, indent=4)
        print(f"解析完成！共整合 {len(self.das_dict)} 个偏远邮编，已保存至: {output_path}")

    def query_zip(self, zip_code):
        """
        查询测试功能
        """
        zip_str = str(zip_code).zfill(5)
        das_type = self.das_dict.get(zip_str, "非偏远地区 (None)")
        print(f"邮编 {zip_str} 的附加费类型为: {das_type}")
        return das_type

if __name__ == "__main__":
    # 测试代码
    file_path = '/Users/qiankun/Desktop/星商/自动报价系统/DAS_Contiguous_Extended_Remote_Alaska_Hawaii_2025.xlsx'
    
    # 获取当前脚本所在目录作为输出目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_json = os.path.join(current_dir, 'das_database.json')
    
    parser = DASParser(file_path)
    if parser.parse():
        parser.save_to_json(output_json)
        
        print("\n--- 随机测试几个邮编 ---")
        # 1002 在 ContUS
        parser.query_zip("01002")
        # 1005 在 ContUSExt
        parser.query_zip("1005")
        # 随便一个不在列表里的
        parser.query_zip("90210")
