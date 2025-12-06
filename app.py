import streamlit as st
import pandas as pd
import re
import time
import json
import google.generativeai as genai
from io import BytesIO

# ==========================================
# 設定頁面資訊
# ==========================================
st.set_page_config(
    page_title="太魯閣語構詞分析器 (Pro)",
    page_icon="📖",
    layout="wide"
)

# ==========================================
# [修正] API Key 設定區塊
# ==========================================
# 優先嘗試從 Streamlit Secrets 讀取，若無則顯示側邊欄輸入框
try:
    if "GEMINI_API_KEY" in st.secrets:
        apiKey = st.secrets["GEMINI_API_KEY"]
    else:
        apiKey = None
except FileNotFoundError:
    apiKey = None

# 如果 Secrets 沒抓到，就在側邊欄顯示輸入框
if not apiKey:
    with st.sidebar:
        st.markdown("### ⚙️ 設定")
        user_api_input = st.text_input("請輸入 Google Gemini API Key", type="password")
        if user_api_input:
            apiKey = user_api_input
        st.caption("若無 API Key，AI 翻譯功能將無法使用，但仍可進行基本的詞法拆解。")

# ==========================================
# 1. 核心字典庫 (整合《語法概論》&《辭典》)
# ==========================================
DICTIONARY = {
    # --- 格位標記與功能詞 ---
    "ka": {"morph": "ka", "gloss": "主格", "meaning": "(主格標記)"},
    "ni": {"morph": "ni", "gloss": "連接詞", "meaning": "和/與"},
    "o": {"morph": "o", "gloss": "主題", "meaning": "(主題標記)"},
    "do": {"morph": "do", "gloss": "助詞", "meaning": "(強調/時間)"},
    "ga": {"morph": "ga", "gloss": "助詞", "meaning": "(特定)"},
    "hug": {"morph": "hug", "gloss": "疑問詞", "meaning": "嗎"},
    "da": {"morph": "da", "gloss": "語尾助詞", "meaning": "了"},
    "saw": {"morph": "saw", "gloss": "像", "meaning": "像/如此"},
    "kiya": {"morph": "kiya", "gloss": "那", "meaning": "那/所以"},
    "kika": {"morph": "kika", "gloss": "連接詞", "meaning": "所以/就是"},
    "nasi": {"morph": "nasi", "gloss": "連接詞", "meaning": "如果"},
    "ana": {"morph": "ana", "gloss": "無定詞", "meaning": "雖然/即使"},
    "ida": {"morph": "ida", "gloss": "助動詞", "meaning": "一定/仍然"},
    "ini": {"morph": "ini", "gloss": "否定", "meaning": "不/沒有"},
    "aji": {"morph": "aji", "gloss": "否定", "meaning": "不是/不要"},
    "uxay": {"morph": "uxay", "gloss": "否定", "meaning": "不是"},
    "iya": {"morph": "iya", "gloss": "否定祈使", "meaning": "別/不要"},
    "ungat": {"morph": "ungat", "gloss": "否定存在", "meaning": "沒有"},
    "niqan": {"morph": "niqan", "gloss": "存在", "meaning": "有"},
    "wada": {"morph": "wada", "gloss": "完成貌.助動", "meaning": "已經/去"},
    "gisu": {"morph": "gisu", "gloss": "進行貌.助動", "meaning": "正在(近)"},
    "gaga": {"morph": "gaga", "gloss": "進行貌.助動", "meaning": "正在(遠)/在那裡"},
    "mha": {"morph": "mha", "gloss": "未來.助動", "meaning": "將"},
    "naa": {"morph": "naa", "gloss": "助動詞", "meaning": "應該"},

    # --- 代名詞 ---
    "ku": {"morph": "ku", "gloss": "1S.主格", "meaning": "我"},
    "su": {"morph": "su", "gloss": "2S.主格/屬格", "meaning": "你/你的"},
    "mu": {"morph": "mu", "gloss": "1S.屬格", "meaning": "我的"},
    "na": {"morph": "na", "gloss": "3S.屬格", "meaning": "他的/尚未"},
    "ta": {"morph": "ta", "gloss": "1PL.包含.主格", "meaning": "我們(包含)"},
    "nami": {"morph": "nami", "gloss": "1PL.排除.主格/屬格", "meaning": "我們(排除)"},
    "namu": {"morph": "namu", "gloss": "2PL.主格/屬格", "meaning": "你們"},
    "deha": {"morph": "deha", "gloss": "3PL.主格/屬格", "meaning": "他們/二"},
    "yaku": {"morph": "yaku", "gloss": "1S.主格(獨立)", "meaning": "我"},
    "isu": {"morph": "isu", "gloss": "2S.主格(獨立)", "meaning": "你"},
    "hiya": {"morph": "hiya", "gloss": "3S.主格(獨立)", "meaning": "他/她/那裡"},
    "kenan": {"morph": "kenan", "gloss": "1S.斜格", "meaning": "對我/被我"},
    "sunan": {"morph": "sunan", "gloss": "2S.斜格", "meaning": "對你/被你"},
    "menan": {"morph": "menan", "gloss": "1PL.排除.斜格", "meaning": "我們"},
    "niyi": {"morph": "niyi", "gloss": "指示", "meaning": "這/這個"},

    # --- A ---
    "adas": {"morph": "adas", "gloss": "帶", "meaning": "帶"},
    "aga": {"morph": "aga", "gloss": "弓", "meaning": "弓"},
    "aguh": {"morph": "aguh", "gloss": "來(命令)", "meaning": "來(叫人來)"},
    "alang": {"morph": "alang", "gloss": "部落", "meaning": "部落/村子"},
    "asi": {"morph": "asi", "gloss": "必須", "meaning": "必須"},
    "asu": {"morph": "asu", "gloss": "船", "meaning": "船"},
    "ayug": {"morph": "ayug", "gloss": "溪流", "meaning": "小溪"},

    # --- B ---
    "babaw": {"morph": "babaw", "gloss": "上面", "meaning": "上面/之後"},
    "babuy": {"morph": "babuy", "gloss": "豬", "meaning": "豬"},
    "baga": {"morph": "baga", "gloss": "手", "meaning": "手"},
    "bais": {"morph": "bais", "gloss": "配偶", "meaning": "配偶"},
    "baki": {"morph": "baki", "gloss": "祖父", "meaning": "祖父/岳父"},
    "balay": {"morph": "balay", "gloss": "真", "meaning": "真的/非常"},
    "balung": {"morph": "balung", "gloss": "蛋", "meaning": "蛋/卵"},
    "baraw": {"morph": "baraw", "gloss": "上面", "meaning": "上面"},
    "bbrigan": {"morph": "bbarig-an", "gloss": "買賣-處所", "meaning": "商店"},
    "begu": {"morph": "begu", "gloss": "湯", "meaning": "湯"},
    "berah": {"morph": "berah", "gloss": "前面", "meaning": "前面/以前"},
    "bgihur": {"morph": "bgihur", "gloss": "風", "meaning": "風"},
    "bhegay": {"morph": "bhegay", "gloss": "白", "meaning": "白色"},
    "bi": {"morph": "bi", "gloss": "很", "meaning": "很"},
    "bilaq": {"morph": "bilaq", "gloss": "小", "meaning": "小"},
    "birat": {"morph": "birat", "gloss": "耳朵", "meaning": "耳朵"},
    "biyi": {"morph": "biyi", "gloss": "工寮", "meaning": "工寮"},
    "blebul": {"morph": "blebul", "gloss": "香蕉", "meaning": "香蕉"},
    "bowyak": {"morph": "bowyak", "gloss": "山豬", "meaning": "山豬"},
    "brebil": {"morph": "brebil", "gloss": "拉", "meaning": "拉/拖"},
    "brunguy": {"morph": "brunguy", "gloss": "背籃", "meaning": "背籃"},
    "btunux": {"morph": "btunux", "gloss": "石頭", "meaning": "石頭"},
    "bubu": {"morph": "bubu", "gloss": "母親", "meaning": "母親"},
    "bubung": {"morph": "bubung", "gloss": "名詞", "meaning": "雨傘"},
    "bunga": {"morph": "bunga", "gloss": "地瓜", "meaning": "地瓜"},
    "buwax": {"morph": "buwax", "gloss": "米", "meaning": "米(未煮)"},

    # --- C ---
    "cicih": {"morph": "cicih", "gloss": "一點", "meaning": "一點點/少"},
    "cimu": {"morph": "cimu", "gloss": "鹽", "meaning": "鹽"},

    # --- D ---
    "dara": {"morph": "dara", "gloss": "血", "meaning": "血"},
    "desun": {"morph": "des-un", "gloss": "帶-受事焦點", "meaning": "被帶"},
    "dgiyaq": {"morph": "dgiyaq", "gloss": "山", "meaning": "山"},
    "dmayaw": {"morph": "d<m>ayaw", "gloss": "<主事焦點>幫忙", "meaning": "幫忙"},
    "dmuuy": {"morph": "d<m>uuy", "gloss": "<主事焦點>拿", "meaning": "拿著/使用"},
    "dowriq": {"morph": "dowriq", "gloss": "眼睛", "meaning": "眼睛"},
    "dqeras": {"morph": "dqeras", "gloss": "臉", "meaning": "臉"},
    "durun": {"morph": "duru-un", "gloss": "委託-受事焦點", "meaning": "被委託"},
    "dxegal": {"morph": "dxegal", "gloss": "地", "meaning": "土地"},

    # --- E ---
    "elug": {"morph": "elug", "gloss": "路", "meaning": "道路"},
    "empgu": {"morph": "emp-gu", "gloss": "未來-發芽", "meaning": "發芽"},
    "empitu": {"morph": "empitu", "gloss": "七", "meaning": "七"},
    "empquyux": {"morph": "emp-quyux", "gloss": "未來-雨", "meaning": "將下雨"},
    "emptgesa": {"morph": "emp-tgesa", "gloss": "主事焦點-教", "meaning": "老師"},
    "empusal": {"morph": "empusal", "gloss": "二十", "meaning": "二十"},

    # --- G ---
    "gamil": {"morph": "gamil", "gloss": "根", "meaning": "根"},
    "gaya": {"morph": "gaya", "gloss": "習俗", "meaning": "規範/習俗"},
    "gbiyan": {"morph": "gbiyan", "gloss": "傍晚", "meaning": "傍晚"},
    "gmquring": {"morph": "g<m>quring", "gloss": "<主事焦點>究", "meaning": "研究"},
    "gsilung": {"morph": "gsilung", "gloss": "海", "meaning": "海"},

    # --- H ---
    "hakaw": {"morph": "hakaw", "gloss": "橋", "meaning": "橋樑"},
    "hangan": {"morph": "hangan", "gloss": "名字", "meaning": "名字"},
    "hici": {"morph": "hici", "gloss": "以後", "meaning": "以後"},
    "hidaw": {"morph": "hidaw", "gloss": "太陽", "meaning": "太陽"},
    "hini": {"morph": "hini", "gloss": "這裡", "meaning": "這裡"},
    "hiyi": {"morph": "hiyi", "gloss": "身體/肉", "meaning": "身體/肉"},
    "hmuya": {"morph": "h<m>uya", "gloss": "<主事焦點>如何", "meaning": "為什麼/如何"},
    "hnici": {"morph": "h<en>ici", "gloss": "<完成貌>留下", "meaning": "留下"},
    "hngkawas": {"morph": "hngkawas", "gloss": "年", "meaning": "年/歲"},
    "huling": {"morph": "huling", "gloss": "狗", "meaning": "狗"},

    # --- I ---
    "idas": {"morph": "idas", "gloss": "月亮", "meaning": "月亮"},
    "idaw": {"morph": "idaw", "gloss": "飯", "meaning": "飯"},
    "ima": {"morph": "ima", "gloss": "誰", "meaning": "誰"},
    "inu": {"morph": "inu", "gloss": "哪裡", "meaning": "哪裡"},

    # --- J ---
    "jiyax": {"morph": "jiyax", "gloss": "日子", "meaning": "日子/時間"},

    # --- K ---
    "kacing": {"morph": "kacing", "gloss": "牛", "meaning": "牛"},
    "kana": {"morph": "kana", "gloss": "全部", "meaning": "全部"},
    "karat": {"morph": "karat", "gloss": "天空", "meaning": "天空/天氣"},
    "kari": {"morph": "kari", "gloss": "名詞", "meaning": "話/語言"},
    "keeman": {"morph": "keeman", "gloss": "晚上", "meaning": "晚上"},
    "kerig": {"morph": "kerig", "gloss": "苧麻", "meaning": "苧麻"},
    "kingal": {"morph": "kingal", "gloss": "一", "meaning": "一"},
    "kjiyax": {"morph": "kjiyax", "gloss": "常常", "meaning": "天天/常常"},
    "klaun": {"morph": "kla-un", "gloss": "知-受事焦點", "meaning": "被知道"},
    "kmari": {"morph": "k<m>ari", "gloss": "<主事焦點>挖", "meaning": "挖掘"},
    "kndusan": {"morph": "kndusan", "gloss": "名詞", "meaning": "生命/生活"},
    "knuwan": {"morph": "knuwan", "gloss": "何時", "meaning": "什麼時候"},
    "kskuy": {"morph": "k-sekuy", "gloss": "靜態-冷", "meaning": "冷"},
    "kuxul": {"morph": "kuxul", "gloss": "喜歡", "meaning": "喜歡/心情"},
    "kuyuh": {"morph": "kuyuh", "gloss": "女人", "meaning": "女人/妻子"},

    # --- L ---
    "lala": {"morph": "lala", "gloss": "多", "meaning": "很多"},
    "laqi": {"morph": "laqi", "gloss": "小孩", "meaning": "小孩"},
    "lukus": {"morph": "lukus", "gloss": "衣服", "meaning": "衣服"},
    "lupung": {"morph": "lupung", "gloss": "朋友", "meaning": "朋友"},

    # --- M ---
    "madas": {"morph": "m-adas", "gloss": "主事焦點-帶", "meaning": "攜帶"},
    "maduk": {"morph": "m-aduk", "gloss": "主事焦點-獵", "meaning": "打獵"},
    "mahun": {"morph": "mah-un", "gloss": "喝-受事焦點", "meaning": "要喝的/飲料"},
    "malu": {"morph": "malu", "gloss": "好", "meaning": "好"},
    "mangal": {"morph": "m-angal", "gloss": "主事焦點-拿", "meaning": "拿取"},
    "manu": {"morph": "manu", "gloss": "疑問詞", "meaning": "什麼"},
    "marig": {"morph": "m-arig", "gloss": "主事焦點-買", "meaning": "買"},
    "matas": {"morph": "m-atas", "gloss": "主事焦點-寫", "meaning": "寫/讀書"},
    "maxal": {"morph": "maxal", "gloss": "十", "meaning": "十"},
    "mbanah": {"morph": "m-banah", "gloss": "主事焦點-紅", "meaning": "紅色"},
    "mddayaw": {"morph": "m-ddayaw", "gloss": "主事焦點-互相幫忙", "meaning": "互相幫忙"},
    "mdrumut": {"morph": "m-drumut", "gloss": "主事焦點-勤勞", "meaning": "勤勞"},
    "mekan": {"morph": "m-ekan", "gloss": "主事焦點-吃", "meaning": "吃"},
    "mekela": {"morph": "m-kela", "gloss": "主事焦點-知", "meaning": "知道/會"},
    "meniq": {"morph": "m-eniq", "gloss": "主事焦點-在", "meaning": "居住/在"},
    "mgarang": {"morph": "m-garang", "gloss": "主事焦點-廣", "meaning": "散播/推廣"},
    "mhapuy": {"morph": "m-hapuy", "gloss": "主事焦點-煮", "meaning": "煮"},
    "mhuqil": {"morph": "m-huqil", "gloss": "主事焦點-死", "meaning": "死亡"},
    "mhuway": {"morph": "m-huway", "gloss": "主事焦點-慷慨", "meaning": "謝謝/慷慨"},
    "mimah": {"morph": "m-imah", "gloss": "主事焦點-喝", "meaning": "喝"},
    "mirit": {"morph": "mirit", "gloss": "羊", "meaning": "羊"},
    "mita": {"morph": "m-ita", "gloss": "主事焦點-看", "meaning": "看"},
    "miyah": {"morph": "m-iyah", "gloss": "主事焦點-來", "meaning": "來"},
    "miying": {"morph": "m-iying", "gloss": "主事焦點-找", "meaning": "尋找/拜訪"},
    "mkla": {"morph": "m-kla", "gloss": "主事焦點-知", "meaning": "知道/會"},
    "mkela": {"morph": "m-kela", "gloss": "主事焦點-知", "meaning": "知道/會"},
    "mkeray": {"morph": "mkeray", "gloss": "主事焦點-堅固", "meaning": "堅固"},
    "mkesa": {"morph": "m-kesa", "gloss": "主事焦點-走", "meaning": "走路"},
    "mnarux": {"morph": "m-narux", "gloss": "主事焦點-病", "meaning": "生病/痛"},
    "mngungu": {"morph": "m-ngungu", "gloss": "主事焦點-怕", "meaning": "害怕"},
    "mnita": {"morph": "m<n>ita", "gloss": "<主事焦點><完成>看", "meaning": "看過"},
    "mniyah": {"morph": "m<n>iyah", "gloss": "主事焦點<完成>-來", "meaning": "來過"},
    "mnkan": {"morph": "m<n>ekan", "gloss": "主事焦點<完成>-吃", "meaning": "吃過"},
    "mowsa": {"morph": "m-owsa", "gloss": "主事焦點-去(未來)", "meaning": "將去"},
    "mqaras": {"morph": "m-qaras", "gloss": "主事焦點-樂", "meaning": "高興/快樂"},
    "mrawa": {"morph": "m-rawa", "gloss": "主事焦點-玩", "meaning": "玩耍"},
    "mrengaw": {"morph": "m-rengaw", "gloss": "主事焦點-說", "meaning": "說"},
    "msangay": {"morph": "m-sangay", "gloss": "主事焦點-休", "meaning": "休息"},
    "msekuy": {"morph": "m-sekuy", "gloss": "主事焦點-冷", "meaning": "變冷/冷"},
    "mseupu": {"morph": "m-seupu", "gloss": "主事焦點-一起", "meaning": "一起"},
    "mskuy": {"morph": "m-sekuy", "gloss": "主事焦點-冷", "meaning": "變冷/冷"},
    "msterung": {"morph": "m-sterung", "gloss": "主事焦點-遇", "meaning": "遇見/結婚"},
    "mtaqi": {"morph": "m-taqi", "gloss": "主事焦點-睡", "meaning": "睡覺"},
    "mtutuy": {"morph": "m-tutuy", "gloss": "主事焦點-起", "meaning": "起床"},
    "musa": {"morph": "m-usa", "gloss": "主事焦點-去", "meaning": "去"},

    # --- N ---
    "naqih": {"morph": "naqih", "gloss": "壞", "meaning": "不好/壞"},
    "ngangut": {"morph": "ngangut", "gloss": "外面", "meaning": "外面"},
    "ngiyaw": {"morph": "ngiyaw", "gloss": "貓", "meaning": "貓"},
    "nii": {"morph": "nii", "gloss": "這", "meaning": "這"},
    "niiq": {"morph": "niiq", "gloss": "在", "meaning": "在(命令)"},

    # --- P ---
    "paah": {"morph": "paah", "gloss": "從", "meaning": "從"},
    "pada": {"morph": "pada", "gloss": "山羌", "meaning": "山羌"},
    "pajiq": {"morph": "pajiq", "gloss": "菜", "meaning": "青菜"},
    "papak": {"morph": "papak", "gloss": "腳", "meaning": "腳"},
    "paru": {"morph": "paru", "gloss": "大", "meaning": "大"},
    "patas": {"morph": "patas", "gloss": "書", "meaning": "書/信"},
    "pblaiq": {"morph": "pe-blaiq", "gloss": "使-好", "meaning": "使平安"},
    "phuqil": {"morph": "p-huqil", "gloss": "使動-死", "meaning": "殺/使死"},
    "pila": {"morph": "pila", "gloss": "錢", "meaning": "錢"},
    "piya": {"morph": "piya", "gloss": "多少", "meaning": "多少"},
    "pndakar": {"morph": "p-en-dakar", "gloss": "叮嚀", "meaning": "叮嚀/囑咐"},
    "pnrjingan": {"morph": "p<n>rajing-an", "gloss": "開始<完成>-名物化", "meaning": "開始/開端"},
    "prajing": {"morph": "prajing", "gloss": "開始", "meaning": "開始"},
    "pratu": {"morph": "pratu", "gloss": "碗", "meaning": "碗"},
    "prengaw": {"morph": "p-rengaw", "gloss": "使動-說", "meaning": "使說/談論"},
    "pspung": {"morph": "p-spung", "gloss": "主事焦點-比", "meaning": "測驗/比賽"},
    "psterung": {"morph": "p-sterung", "gloss": "使動-遇", "meaning": "使遇見/使結婚"},
    "ptasan": {"morph": "patas-an", "gloss": "寫-處所", "meaning": "學校"},
    "pucing": {"morph": "pucing", "gloss": "名詞", "meaning": "獵刀"},
    "pupu": {"morph": "pupu", "gloss": "斧頭", "meaning": "斧頭"},
    "pusu": {"morph": "pusu", "gloss": "名詞", "meaning": "根源/主要"},

    # --- Q ---
    "qbsuran": {"morph": "qbsuran", "gloss": "兄姊", "meaning": "哥哥/姊姊"},
    "qduriq": {"morph": "qduriq", "gloss": "逃", "meaning": "逃跑"},
    "qempah": {"morph": "q<em?>pah", "gloss": "<主事焦點>工作", "meaning": "工作"},
    "qhuni": {"morph": "qhuni", "gloss": "樹", "meaning": "樹木"},
    "qita": {"morph": "qita", "gloss": "看", "meaning": "看"},
    "qmita": {"morph": "q<m>ita", "gloss": "<主事焦點>看", "meaning": "看"},
    "qmpahan": {"morph": "qmpah-an", "gloss": "田", "meaning": "田地"},
    "qmpringan": {"morph": "qmpringan", "gloss": "名詞", "meaning": "團隊/基金會"},
    "qmuyux": {"morph": "q<m>uyux", "gloss": "<主事焦點>雨", "meaning": "下雨"},
    "qowlit": {"morph": "qowlit", "gloss": "鼠", "meaning": "老鼠"},
    "qpahun": {"morph": "qmpah-un", "gloss": "工作-受事焦點", "meaning": "工作(被做)"},
    "qsiya": {"morph": "qsiya", "gloss": "水", "meaning": "水"},
    "qsurux": {"morph": "qsurux", "gloss": "魚", "meaning": "魚"},
    "qtaan": {"morph": "qta-an", "gloss": "看-處所焦點", "meaning": "被看見/看見之處"},
    "quwaq": {"morph": "quwaq", "gloss": "嘴", "meaning": "嘴巴"},
    "quyu": {"morph": "quyu", "gloss": "蛇", "meaning": "蛇"},

    # --- R ---
    "rapit": {"morph": "rapit", "gloss": "飛鼠", "meaning": "飛鼠"},
    "rbagan": {"morph": "rbagan", "gloss": "夏天", "meaning": "夏天"},
    "risaw": {"morph": "risaw", "gloss": "青年", "meaning": "男青年"},
    "rmengaw": {"morph": "r<m>ngaw", "gloss": "<主事焦點>說", "meaning": "說"},
    "rnabaw": {"morph": "rnabaw", "gloss": "名詞", "meaning": "葉子"},
    "rngagan": {"morph": "rngag-an", "gloss": "說-處所焦點", "meaning": "告訴/說"},
    "rngagi": {"morph": "rngag-i", "gloss": "說-祈使", "meaning": "告訴(命令)"},
    "rngagun": {"morph": "rngag-un", "gloss": "說-受事焦點", "meaning": "被說/要說的話"},
    "rudan": {"morph": "rudan", "gloss": "名詞", "meaning": "老人/祖先"},
    "rudux": {"morph": "rudux", "gloss": "雞", "meaning": "雞"},
    "ruwan": {"morph": "ruwan", "gloss": "裡面", "meaning": "裡面"},

    # --- S ---
    "saman": {"morph": "saman", "gloss": "名詞", "meaning": "明天"},
    "samat": {"morph": "samat", "gloss": "獵物", "meaning": "野獸/獵物"},
    "sapah": {"morph": "sapah", "gloss": "家", "meaning": "家/房子"},
    "sapuh": {"morph": "sapuh", "gloss": "藥", "meaning": "藥"},
    "sari": {"morph": "sari", "gloss": "芋頭", "meaning": "芋頭"},
    "saw": {"morph": "saw", "gloss": "像", "meaning": "像/如此"},
    "sayang": {"morph": "sayang", "gloss": "名詞", "meaning": "現在/今天"},
    "seejiq": {"morph": "seejiq", "gloss": "名詞", "meaning": "人/賽德克"},
    "senaw": {"morph": "senaw", "gloss": "男人", "meaning": "男人"},
    "shiga": {"morph": "shiga", "gloss": "昨天", "meaning": "昨天"},
    "shungi": {"morph": "shungi", "gloss": "忘記", "meaning": "忘記"},
    "sibus": {"morph": "sibus", "gloss": "甘蔗", "meaning": "甘蔗"},
    "sinaw": {"morph": "sinaw", "gloss": "酒", "meaning": "酒"},
    "siyang": {"morph": "siyang", "gloss": "豬肉", "meaning": "肥豬肉"},
    "siyaw": {"morph": "siyaw", "gloss": "旁邊", "meaning": "旁邊"},
    "smiling": {"morph": "s-m-iling", "gloss": "主事焦點-問", "meaning": "問"},
    "smku": {"morph": "s<m>ku", "gloss": "<主事焦點>存", "meaning": "保存/存放"},
    "smluhay": {"morph": "s<m>luhay", "gloss": "<主事焦點>學", "meaning": "學習"},
    "smmalu": {"morph": "s<m>malu", "gloss": "<主事焦點>做", "meaning": "製作/研發"},
    "smepug": {"morph": "s<m>epug", "gloss": "<主事焦點>數", "meaning": "數/盤點"},
    "smruwa": {"morph": "s<m>ruwa", "gloss": "<主事焦點>答應", "meaning": "答應"},
    "snduray": {"morph": "snduray", "gloss": "名詞", "meaning": "最近"},
    "sngulun": {"morph": "snegul-un", "gloss": "跟隨-受事焦點", "meaning": "被跟隨"},
    "snhiyi": {"morph": "snhiyi", "gloss": "信", "meaning": "相信"},
    "speriq": {"morph": "speriq", "gloss": "名詞", "meaning": "草"},
    "swai": {"morph": "swai", "gloss": "弟妹", "meaning": "弟弟/妹妹"},

    # --- T ---
    "talang": {"morph": "talang", "gloss": "跑", "meaning": "跑(命令)"},
    "tama": {"morph": "tama", "gloss": "父親", "meaning": "父親"},
    "tasil": {"morph": "tasil", "gloss": "名詞", "meaning": "大石頭"},
    "tduwa": {"morph": "tduwa", "gloss": "可以", "meaning": "可以"},
    "teru": {"morph": "teru", "gloss": "三", "meaning": "三"},
    "tmalang": {"morph": "t<m>alang", "gloss": "<主事焦點>跑", "meaning": "跑"},
    "tmapaq": {"morph": "t<m>apaq", "gloss": "<主事焦點>拍", "meaning": "拍打/游泳"},
    "tmgesa": {"morph": "t<m>gesa", "gloss": "<主事焦點>教", "meaning": "教導"},
    "tmgsa": {"morph": "tmgsa", "gloss": "教導", "meaning": "教導"},
    "tminun": {"morph": "t<m>inun", "gloss": "<主事焦點>織", "meaning": "編織"},
    "tnpusu": {"morph": "te-ne-pusu", "gloss": "扎根/定居", "meaning": "扎根"},
    "trima": {"morph": "trima", "gloss": "洗澡", "meaning": "洗澡"},
    "truku": {"morph": "Truku", "gloss": "專有名詞", "meaning": "太魯閣"},
    "truma": {"morph": "truma", "gloss": "下面", "meaning": "下面"},
    "tunux": {"morph": "tunux", "gloss": "頭", "meaning": "頭"},

    # --- U ---
    "uqan": {"morph": "uq-an", "gloss": "吃-處所焦點", "meaning": "吃飯的地方"},
    "uqi": {"morph": "uq-i", "gloss": "吃-祈使", "meaning": "吃(命令)"},
    "uqun": {"morph": "uq-un", "gloss": "吃-受事焦點", "meaning": "要吃的/食物"},
    "uri": {"morph": "uri", "gloss": "也", "meaning": "也"},
    "utux": {"morph": "utux", "gloss": "靈", "meaning": "神/鬼/祖靈"},
    "uwa": {"morph": "uwa", "gloss": "少女", "meaning": "女青年"},
    "uyas": {"morph": "uyas", "gloss": "歌", "meaning": "歌"},

    # --- Y ---
    "yayu": {"morph": "yayu", "gloss": "名詞", "meaning": "小刀"},
    "yayung": {"morph": "yayung", "gloss": "河", "meaning": "河流"}
}

# ==========================================
# 2. 構詞規則引擎 (Rule-Based Engine)
# ==========================================
def analyze_morphology(word):
    analysis = {"morph": word, "gloss": "???", "meaning": ""}
    
    # 規則 1: 主事焦點 (AF) 前綴 m-, me-, em-, tm-, km-, sm-
    if re.match(r'^m[a-z]+', word) and not word.startswith("ma"):
        if word.startswith("me"):
            root = word[2:]
            return {"morph": f"me-{root}", "gloss": "主事焦點-", "meaning": "(動詞)"}
        elif word.startswith("m"):
            root = word[1:]
            # 簡單判斷：若剩餘部分有母音，可能是 m-root
            if any(char in "aeiou" for char in root):
                return {"morph": f"m-{root}", "gloss": "主事焦點-", "meaning": "(動詞)"}
    
    # 特殊前綴偵測
    if word.startswith("sm") and len(word) > 3:
         root = word[2:]
         return {"morph": f"s<m>{root}", "gloss": "<主事焦點>", "meaning": "(動詞)"}
    if word.startswith("km") and len(word) > 3:
         root = word[2:]
         return {"morph": f"k<m>{root}", "gloss": "<主事焦點>", "meaning": "(動詞)"}
    if word.startswith("tm") and len(word) > 3:
         root = word[2:]
         return {"morph": f"t<m>{root}", "gloss": "<主事焦點>", "meaning": "(動詞)"}
    if word.startswith("gm") and len(word) > 3:
         root = word[2:]
         return {"morph": f"g<m>{root}", "gloss": "<主事焦點>", "meaning": "(動詞)"}

    # 規則 2: 中綴 <m>, <n>
    if len(word) > 3 and word[1] in ['m', 'n'] and word[2] in "aeiou":
        infix = word[1]
        root = word[0] + word[2:]
        gloss = "<主事焦點>" if infix == 'm' else "<完成貌>"
        return {"morph": f"{word[0]}<{infix}>{word[2:]}", "gloss": gloss, "meaning": "(動詞)"}
    
    # 規則 3: 受事焦點 (PF) -un
    if word.endswith("un"):
        root = word[:-2]
        return {"morph": f"{root}-un", "gloss": "-受事焦點", "meaning": "(被動/未來)"}

    # 規則 4: 處所焦點 (LF) -an
    if word.endswith("an"):
        root = word[:-2]
        return {"morph": f"{root}-an", "gloss": "-處所焦點", "meaning": "(處所/過去)"}

    # 規則 5: 祈使 (IMP) -i
    if word.endswith("i"):
        root = word[:-1]
        return {"morph": f"{root}-i", "gloss": "-祈使", "meaning": "(命令)"}

    # 規則 6: 未來/非實現 (FUT) emp-
    if word.startswith("emp"):
        root = word[3:]
        return {"morph": f"emp-{root}", "gloss": "未來-", "meaning": "將..."}
    
    # 規則 7: 使動 (Causative) p-, pe-
    if word.startswith("pe"):
        root = word[2:]
        return {"morph": f"pe-{root}", "gloss": "使動-", "meaning": "使..."}
    if word.startswith("p") and len(word) > 2 and word[1] not in "aeiou":
        root = word[1:]
        return {"morph": f"p-{root}", "gloss": "使動-", "meaning": "使..."}

    return analysis

# ==========================================
# 3. AI 翻譯 API (Google Gemini) - [修正] 
# ==========================================
def call_ai_translation(text, target_lang, gloss_context=""):
    # 若沒有 API Key 則跳過，避免報錯
    if not apiKey:
        return None

    # 設定 Key
    try:
        genai.configure(api_key=apiKey)
        model = genai.GenerativeModel('gemini-pro')

        if target_lang == 'truku':
            prompt = f"請將以下中文句子翻譯成太魯閣族語(Truku)。直接給出翻譯後的族語句子即可，不要包含其他解釋或拼音。\n句子：{text}"
        else:
            # RAG-Chain Prompt
            prompt = f"""
            你是一個精通太魯閣語(Truku)與中文的語言學家。請進行以下翻譯任務：
            1. **結構對應 (Structural Alignment)**：參考提供的 [詞法分析] (Gloss)，理解原句的語法結構（主事/受事焦點、時態、格位）。
            2. **直譯 (Literal Translation)**：先在心中進行詞對詞的直譯。
            3. **語意優化 (Semantic Refinement)**：將直譯結果調整為通順的中文，但**嚴格保留原句的焦點與語態**（例如：受事焦點句應翻成「被...」或「把...」結構）。

            原文：{text}
            詞法分析參考：{gloss_context}

            請直接輸出翻譯結果，不要包含任何解釋或前言後語。
            """
        
        response = model.generate_content(prompt)
        return response.text.strip()
    
    except Exception as e:
        # 在此處不直接使用 st.error，而是回傳 None，讓主程式判斷
        print(f"AI API Error: {e}")
        return None

# ==========================================
# 介面邏輯
# ==========================================

st.title("太魯閣語構詞分析器 (Pro)")
st.markdown("---")

# 輸入區
col1, col2 = st.columns([3, 1])
with col1:
    input_text = st.text_area("請輸入句子 (族語或中文)", height=100, placeholder="例：Mkla su rmngaw kari Truku hug?")
with col2:
    st.write("範例：")
    if st.button("範例 1"):
        input_text = "Mkla su rmngaw kari Truku hug?"
    if st.button("範例 2"):
        input_text = "Empquyux ka saman da, asi su ka madas bubung."

# 分析按鈕
if st.button("開始分析", type="primary"):
    if not input_text:
        st.warning("請輸入文字")
    else:
        with st.spinner("分析中..."):
            # 1. 判斷語言模式
            is_chinese = any("\u4e00" <= char <= "\u9fff" for char in input_text)
            
            source_text = input_text
            translation_text = ""

            # 2. 中文 -> 族語 (AI 翻譯)
            if is_chinese:
                # 若無 Key，必須停止，因為中文無法直接查字典分析
                if not apiKey:
                    st.error("您輸入的是中文，需要設定 API Key 才能進行 AI 翻譯轉換為族語。")
                    st.stop()
                
                ai_translation = call_ai_translation(source_text, 'truku')
                if ai_translation:
                    translation_text = source_text
                    source_text = ai_translation
                else:
                    st.error("AI 翻譯服務連線失敗，請檢查 Key 是否正確或額度是否足夠。")
                    st.stop()

            # 3. 構詞分析
            clean_text = re.sub(r'[.,?!;:，。？！；：]', '', source_text).lower()
            raw_words = source_text.split()
            
            analyzed_words = []
            for word in raw_words:
                clean_word = re.sub(r'[.,?!;:，。？！；：]', '', word).lower()
                if clean_word in DICTIONARY:
                    data = DICTIONARY[clean_word]
                    analyzed_words.append({"original": word, "morph": data["morph"], "gloss": data["gloss"], "meaning": data["meaning"]})
                else:
                    guess = analyze_morphology(clean_word)
                    analyzed_words.append({"original": word, "morph": guess["morph"], "gloss": guess["gloss"], "meaning": guess["meaning"]})

            # 4. 族語 -> 中文 (AI 翻譯)
            if not is_chinese:
                gloss_context = " ".join([f"{w['original']}({w['gloss']}/{w['meaning']})" for w in analyzed_words if w['gloss'] != "???"])
                
                if apiKey:
                    ai_translation = call_ai_translation(source_text, 'chinese', gloss_context)
                    translation_text = ai_translation if ai_translation else "(翻譯生成失敗，請檢查 API Key)"
                else:
                    translation_text = "(未設定 API Key，無法顯示 AI 翻譯)"

            # 5. 顯示結果 - 四行樣式 (● 開頭)
            st.markdown("### 四行標註分析")
            
            html_output = f"""
            <div style="font-family: monospace; font-size: 16px; line-height: 1.8; background-color: #f8f9fa; padding: 20px; border-radius: 10px;">
                <div style="margin-bottom: 8px;"><span style="color: #e11d48; font-weight: bold;">●</span> {' '.join([w['original'] for w in analyzed_words])}</div>
                <div style="margin-bottom: 8px;"><span style="color: #2563eb; font-weight: bold;">●</span> {' '.join([w['morph'] for w in analyzed_words])}</div>
                <div style="margin-bottom: 8px;"><span style="color: #059669; font-weight: bold;">●</span> {' '.join([w['gloss'] for w in analyzed_words])}</div>
                <div style="margin-top: 12px; font-weight: bold; border-top: 1px solid #e5e7eb; padding-top: 8px;"><span style="color: #d97706;">●</span> {translation_text}</div>
            </div>
            """
            st.markdown(html_output, unsafe_allow_html=True)

            # 6. 匯出功能 (CSV)
            csv_data = []
            csv_data.append(["Line", "Content"])
            csv_data.append(["1", ' '.join([w['original'] for w in analyzed_words])])
            csv_data.append(["2", ' '.join([w['morph'] for w in analyzed_words])])
            csv_data.append(["3", ' '.join([w['gloss'] for w in analyzed_words])])
            csv_data.append(["4", translation_text])
            
            df_export = pd.DataFrame(csv_data)
            csv = df_export.to_csv(index=False, header=False).encode('utf-8-sig')
            
            st.download_button(
                label="匯出 Excel (CSV)",
                data=csv,
                file_name='truku_analysis.csv',
                mime='text/csv',
            )

st.markdown("---")
st.caption("資料來源參考：《太魯閣語語法概論》 | 設計用途：族語教學與語料保存")
