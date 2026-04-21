"""
处理材料对比结果，计算每个城市的制冷节能和制热节能
将结果汇总为output.csv
"""

import pandas as pd
import os
from pathlib import Path


def process_energy_savings(input_file: str, output_file: str = 'output.csv'):
    """
    处理材料对比结果，提取每个省份的最大节能值
    
    参数:
        input_file: 输入的Excel文件路径
        output_file: 输出的CSV文件路径
    """
    # 读取Excel文件
    print(f"正在读取文件: {input_file}")
    df = pd.read_excel(input_file, engine='openpyxl')
    
    print(f"数据形状: {df.shape}")
    print(f"列名: {df.columns.tolist()}")
    
    # 检查必要的列是否存在
    required_columns = ['EPW', 'Saving_cooling_energy_MJ_per_m2', 'Saving_heating_energy_MJ_per_m2']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"缺少必要的列: {missing_columns}")
    
    # 按省份（EPW）分组，提取最大值
    print("\n正在处理数据...")
    results = []
    
    for province, group in df.groupby('EPW'):
        # 提取制冷节能的最大值
        max_cooling = group['Saving_cooling_energy_MJ_per_m2'].max()
        
        # 提取制热节能的最大值
        max_heating = group['Saving_heating_energy_MJ_per_m2'].max()
        
        # 计算总节能
        saving_total = max_cooling + max_heating
        
        results.append({
            'Province': province,
            'Saving_cooling_energy_MJ_per_m2': max_cooling,
            'Saving_heating_energy_MJ_per_m2': max_heating,
            'Saving_Total': saving_total
        })
        
        print(f"  {province}: 制冷节能={max_cooling:.2f}, 制热节能={max_heating:.2f}, 总节能={saving_total:.2f}")
    
    # 创建结果DataFrame
    result_df = pd.DataFrame(results)
    
    # 按省份名称排序
    result_df = result_df.sort_values('Province')
    
    # 保存为CSV
    output_path = Path(input_file).parent / output_file
    result_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    
    print(f"\n处理完成！结果已保存到: {output_path}")
    print(f"共处理 {len(result_df)} 个省份")
    
    return result_df


if __name__ == '__main__':
    # 获取脚本所在目录
    script_dir = Path(__file__).parent
    
    # 默认输入文件路径
    input_file = script_dir / 'output' / 'comparison' / 'material_radiative_cooling_comparison_all.xlsx'
    
    # 检查文件是否存在
    if not input_file.exists():
        print(f"错误: 找不到输入文件: {input_file}")
        print("请确保文件路径正确")
        exit(1)
    
    # 处理数据
    result_df = process_energy_savings(str(input_file))
    
    # 显示结果摘要
    print("\n结果摘要:")
    print(result_df.to_string(index=False))
