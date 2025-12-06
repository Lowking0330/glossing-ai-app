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
# API Key 設定區塊
# ==========================================
apiKey = None

try:
    if "GEMINI_API_KEY" in st.secrets:
        apiKey = st.secrets["GEMINI_API_KEY"]
except FileNotFoundError:
    pass 

if not apiKey:
    with st.sidebar:
        st.markdown("### ⚙️ 系統設定")
        user_api_input = st.text_input("請輸入 Google Gemini API Key", type="password")
        if user_api_input:
            apiKey = user_api_input
        st.caption("ℹ️ 若無 API Key，僅能進行詞法拆解，無法使用整句翻譯。")
        st.markdown("---")

with st.sidebar:
    if apiKey:
        st.success(f"✅ API Key 已載入")
        st.caption("🚀 目前使用模型：gemini-2.5-flash (快取開啟)")
    else:
        st.warning("⚠️ 未偵測到 API Key")

# ==========================================
# 1. 核心字典庫 (快取)
# ==========================================
@st.cache_data(persist=True)
def get_dictionary():
    return {
        # --- 新範例單字 ---
        "mtalux": {"morph": "mtalux", "gloss": "熱", "meaning": "熱/燙"},
        "mring": {"morph": "mring", "gloss": "髒/汗", "meaning": "流汗/髒"},
        "bhangan": {"morph": "bhangan", "gloss": "聽", "meaning": "聽到/聽聞"},
        "meiyah": {"morph": "m-iyah", "gloss": "主事焦點-來", "meaning": "來(異體)"},
        "msa": {"morph": "msa", "gloss": "說", "meaning": "說/如此"},
        "mlatat": {"morph": "m-latat", "gloss": "主事焦點-出", "meaning": "出門/出去"},
        "snguhi": {"morph": "snguh-i", "gloss": "忘記-祈使", "meaning": "忘記(別忘)"},
        # --- 原有單字 ---
        "tmkuy": {"morph": "t<m>kuy", "gloss": "<主事焦點>種", "meaning": "種植/播種"},
        "tnkuyan": {"morph": "tnkuy-an", "gloss": "田", "meaning": "田地/耕地"},
        "masu": {"morph": "masu", "gloss": "小米", "meaning": "小米"},
        "daya": {"morph": "daya", "gloss": "上游/山上", "meaning": "上游/山上"},
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
        "adas": {"morph": "adas", "gloss": "帶", "meaning": "帶"},
        "aga": {"morph": "aga", "gloss": "弓", "meaning": "弓"},
        "aguh": {"morph": "aguh", "gloss": "來(命令)", "meaning": "來(叫人來)"},
        "alang": {"morph": "alang", "gloss": "部落", "meaning": "部落/村子"},
        "asi": {"morph": "asi", "gloss": "必須", "meaning": "必須"},
        "asu": {"morph": "asu", "gloss": "船", "meaning": "船"},
        "ayug": {"morph": "ayug", "gloss": "溪流", "meaning": "小溪"},
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
        "cicih": {"morph": "cicih", "gloss": "一點", "meaning": "一點點/少"},
        "cimu": {"morph": "cimu", "gloss": "鹽", "meaning": "鹽"},
        "dara": {"morph": "dara", "gloss": "血", "meaning": "血"},
        "desun": {"morph": "des-un", "gloss": "帶-受事焦點", "meaning": "被帶"},
        "dgiyaq": {"morph": "dgiyaq", "gloss": "山", "meaning": "山"},
        "dmayaw": {"morph": "d<m>ayaw", "gloss": "<主事焦點>幫忙", "meaning": "幫忙"},
        "dmuuy": {"morph": "d<m>uuy", "gloss": "<主事焦點>拿", "meaning": "拿著/使用"},
        "dowriq": {"morph": "dowriq", "gloss": "眼睛", "meaning": "眼睛"},
        "dqeras": {"morph": "dqeras", "gloss": "臉", "meaning": "臉"},
        "durun": {"morph": "duru-un", "gloss": "委託-受事焦點", "meaning": "被委託"},
        "dxegal": {"morph": "dxegal", "gloss": "地", "meaning": "土地"},
        "elug": {"morph": "elug", "gloss": "路", "meaning": "道路"},
        "empgu": {"morph": "emp-gu", "gloss": "未來-發芽", "meaning": "發芽"},
        "empitu": {"morph": "empitu", "gloss": "七", "meaning": "七"},
        "empquyux": {"morph": "emp-quyux", "gloss": "未來-雨", "meaning": "將下雨"},
        "emptgesa": {"morph": "emp-tgesa", "gloss": "主事焦點-教", "meaning": "老師"},
        "empusal": {"morph": "empusal", "gloss": "二十", "meaning": "二十"},
        "gamil": {"morph": "gamil", "gloss": "根", "meaning": "根"},
        "gaya": {"morph": "gaya", "gloss": "習俗", "meaning": "規範/習俗"},
        "gbiyan": {"morph": "gbiyan", "gloss": "傍晚", "meaning": "傍晚"},
        "gmquring": {"morph": "g<m>quring", "gloss": "<主事焦點>究", "meaning": "研究"},
        "gsilung": {"morph": "gsilung", "gloss": "海", "meaning": "海"},
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
        "idas": {"morph": "idas", "gloss": "月亮", "meaning": "月亮"},
        "idaw": {"morph": "idaw", "gloss": "飯", "meaning": "飯"},
        "ima": {"morph": "ima", "gloss": "誰", "meaning": "誰"},
        "inu": {"morph": "inu", "gloss": "哪裡", "meaning": "哪裡"},
        "jiyax": {"morph": "jiyax", "gloss": "日子", "meaning": "日子/時間"},
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
        "lala": {"morph": "lala", "gloss": "多", "meaning": "很多"},
        "laqi": {"morph": "laqi", "gloss": "小孩", "meaning": "小孩"},
        "lukus": {"morph": "lukus", "gloss": "衣服", "meaning": "衣服"},
        "lupung": {"morph": "lupung", "gloss": "朋友", "meaning": "朋友"},
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
        "mnkan": {"
