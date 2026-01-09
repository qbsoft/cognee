"""
中文转拼音工具模块

用于将中文租户名转换为拼音格式的邮箱前缀
"""
import re


def chinese_to_pinyin(text: str) -> str:
    """
    将中文文本转换为拼音（简化版）
    
    这是一个简化实现，使用拼音映射表处理常用汉字。
    对于复杂场景，建议使用 pypinyin 库。
    
    Args:
        text: 中文文本
        
    Returns:
        str: 拼音字符串（小写，无空格）
        
    Examples:
        >>> chinese_to_pinyin("北京科技")
        'beijingkeji'
        >>> chinese_to_pinyin("测试公司")
        'ceshigongsi'
    """
    # 简化实现：使用常用汉字拼音映射表
    # 在生产环境建议使用 pypinyin 库: from pypinyin import lazy_pinyin
    
    # 常用汉字拼音映射（可扩展）
    pinyin_map = {
        # 常用字
        '北': 'bei', '京': 'jing', '科': 'ke', '技': 'ji', '公': 'gong', '司': 'si',
        '上': 'shang', '海': 'hai', '软': 'ruan', '件': 'jian', '测': 'ce', '试': 'shi',
        '深': 'shen', '圳': 'zhen', '广': 'guang', '州': 'zhou', '杭': 'hang',
        '成': 'cheng', '都': 'dou', '武': 'wu', '汉': 'han', '西': 'xi', '安': 'an',
        '南': 'nan', '宁': 'ning', '重': 'chong', '庆': 'qing', '天': 'tian', '津': 'jin',
        '长': 'chang', '沙': 'sha', '郑': 'zheng', '合': 'he', '肥': 'fei',
        '福': 'fu', '建': 'jian', '厦': 'xia', '门': 'men', '青': 'qing', '岛': 'dao',
        '大': 'da', '连': 'lian', '沈': 'shen', '阳': 'yang', '哈': 'ha', '尔': 'er',
        '滨': 'bin', '石': 'shi', '家': 'jia', '庄': 'zhuang', '太': 'tai', '原': 'yuan',
        '苏': 'su', '无': 'wu', '锡': 'xi', '常': 'chang', '宁': 'ning', '波': 'bo',
        '温': 'wen', '台': 'tai', '绍': 'shao', '兴': 'xing', '金': 'jin', '华': 'hua',
        '嘉': 'jia', '湖': 'hu', '珠': 'zhu', '中': 'zhong', '山': 'shan', '江': 'jiang',
        '东': 'dong', '佛': 'fo', '惠': 'hui', '汕': 'shan', '头': 'tou', '湛': 'zhan',
        '茂': 'mao', '名': 'ming', '肇': 'zhao', '清': 'qing', '韶': 'shao', '关': 'guan',
        '河': 'he', '源': 'yuan', '梅': 'mei', '潮': 'chao', '揭': 'jie', '云': 'yun',
        '浮': 'fu', '阳': 'yang', '信': 'xin', '息': 'xi', '新': 'xin', '乡': 'xiang',
        '鹤': 'he', '壁': 'bi', '焦': 'jiao', '作': 'zuo', '濮': 'pu', '许': 'xu',
        '漯': 'luo', '三': 'san', '门': 'men', '峡': 'xia', '商': 'shang', '丘': 'qiu',
        '周': 'zhou', '口': 'kou', '驻': 'zhu', '马': 'ma', '店': 'dian', '南': 'nan',
        '洛': 'luo', '开': 'kai', '封': 'feng', '平': 'ping', '顶': 'ding', '鹰': 'ying',
        '潭': 'tan', '景': 'jing', '德': 'de', '镇': 'zhen', '赣': 'gan', '抚': 'fu',
        '宜': 'yi', '春': 'chun', '吉': 'ji', '上': 'shang', '饶': 'rao', '九': 'jiu',
        '萍': 'ping', '新': 'xin', '余': 'yu', '鹰': 'ying', '贵': 'gui', '溪': 'xi',
        '瑞': 'rui', '昌': 'chang', '临': 'lin', '川': 'chuan', '宁': 'ning', '德': 'de',
        '智': 'zhi', '能': 'neng', '数': 'shu', '据': 'ju', '网': 'wang', '络': 'luo',
        '信': 'xin', '技': 'ji', '电': 'dian', '子': 'zi', '通': 'tong', '讯': 'xun',
        '移': 'yi', '动': 'dong', '联': 'lian', '互': 'hu', '媒': 'mei', '体': 'ti',
        '传': 'chuan', '播': 'bo', '文': 'wen', '化': 'hua', '教': 'jiao', '育': 'yu',
        '培': 'pei', '训': 'xun', '咨': 'zi', '询': 'xun', '服': 'fu', '务': 'wu',
        '管': 'guan', '理': 'li', '人': 'ren', '力': 'li', '资': 'zi', '产': 'chan',
        '财': 'cai', '务': 'wu', '投': 'tou', '资': 'zi', '基': 'ji', '金': 'jin',
        '证': 'zheng', '券': 'quan', '保': 'bao', '险': 'xian', '银': 'yin', '行': 'xing',
        '租': 'zu', '赁': 'lin', '物': 'wu', '流': 'liu', '运': 'yun', '输': 'shu',
        '仓': 'cang', '储': 'chu', '配': 'pei', '送': 'song', '快': 'kuai', '递': 'di',
        '餐': 'can', '饮': 'yin', '酒': 'jiu', '店': 'dian', '旅': 'lv', '游': 'you',
        '娱': 'yu', '乐': 'le', '健': 'jian', '康': 'kang', '医': 'yi', '疗': 'liao',
        '药': 'yao', '品': 'pin', '器': 'qi', '械': 'xie', '美': 'mei', '容': 'rong',
        '装': 'zhuang', '饰': 'shi', '设': 'she', '计': 'ji', '广': 'guang', '告': 'gao',
        '营': 'ying', '销': 'xiao', '策': 'ce', '划': 'hua', '品': 'pin', '牌': 'pai',
        '推': 'tui', '展': 'zhan', '会': 'hui', '议': 'yi', '展': 'zhan', '览': 'lan',
        '演': 'yan', '出': 'chu', '影': 'ying', '视': 'shi', '音': 'yin', '乐': 'le',
        '艺': 'yi', '术': 'shu', '画': 'hua', '廊': 'lang', '博': 'bo', '物': 'wu',
        '图': 'tu', '书': 'shu', '馆': 'guan', '学': 'xue', '校': 'xiao', '院': 'yuan',
        '所': 'suo', '中': 'zhong', '心': 'xin', '站': 'zhan', '部': 'bu', '局': 'ju',
        '厅': 'ting', '处': 'chu', '科': 'ke', '股': 'gu', '组': 'zu', '队': 'dui',
        '团': 'tuan', '社': 'she', '协': 'xie', '委': 'wei', '会': 'hui', '联': 'lian',
        '盟': 'meng', '业': 'ye', '企': 'qi', '商': 'shang', '贸': 'mao', '易': 'yi',
        '进': 'jin', '出': 'chu', '口': 'kou', '外': 'wai', '国': 'guo', '际': 'ji',
        '全': 'quan', '球': 'qiu', '世': 'shi', '界': 'jie', '亚': 'ya', '欧': 'ou',
        '美': 'mei', '非': 'fei', '澳': 'ao', '洲': 'zhou', '港': 'gang', '澳': 'ao',
        '台': 'tai', '湾': 'wan', '省': 'sheng', '市': 'shi', '县': 'xian', '区': 'qu',
        '镇': 'zhen', '村': 'cun', '街': 'jie', '道': 'dao', '路': 'lu', '巷': 'xiang',
        '弄': 'nong', '号': 'hao', '楼': 'lou', '层': 'ceng', '室': 'shi', '座': 'zuo',
        # 添加缺少的常用字
        '户': 'hu', '主': 'zhu', '用': 'yong', '员': 'yuan', '价': 'jia', '值': 'zhi',
    }
    
    result = []
    for char in text:
        if char in pinyin_map:
            result.append(pinyin_map[char])
        elif char.isalpha() or char.isdigit():
            # 保留英文字母和数字
            result.append(char.lower())
        # 忽略其他字符（标点、空格等）
    
    return ''.join(result)


def generate_tenant_admin_email(tenant_name: str) -> str:
    """
    根据租户名生成管理员邮箱
    
    Args:
        tenant_name: 租户名称
        
    Returns:
        str: 管理员邮箱地址
        
    Examples:
        >>> generate_tenant_admin_email("北京科技")
        'beijingkeji@tyersoft.com'
    """
    pinyin = chinese_to_pinyin(tenant_name)
    
    # 如果转换后为空（全是特殊字符），使用默认值
    if not pinyin:
        pinyin = "tenant"
    
    return f"{pinyin}@tyersoft.com"


# 测试代码
if __name__ == "__main__":
    test_cases = [
        "北京科技",
        "上海软件",
        "深圳智能",
        "测试公司",
        "ABC科技",
        "123公司",
    ]
    
    for name in test_cases:
        email = generate_tenant_admin_email(name)
        print(f"{name:15s} -> {email}")
