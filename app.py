import streamlit as st
import google.generativeai as genai

# 設定網頁標題與介面
st.set_page_config(page_title="太魯閣語語法標註助手", page_icon="🏔️", layout="wide")

st.title("🏔️ 太魯閣語自動語法標註系統")
st.markdown("依據**《太魯閣語語法概論》**體系進行分析，並透過表格精準對齊。")

# 側邊欄：設定 API Key
with st.sidebar:
    st.header("設定")
    api_key = st.text_input("輸入 Google AI API Key", type="password")
    st.markdown("[如何取得 Google API Key?](https://aistudio.google.com/app/apikey)")
    st.info("本工具使用 Gemini-2.0-Flash 模型。")

# 主輸入區
truku_input = st.text_area("請輸入太魯閣語句子：", height=100, placeholder="例如：Mkla su rmngaw kari Truku hug?")

# 定義語法規則 System Prompt
grammar_rules = """
你是一位專精於《太魯閣語語法概論》(2018, 李佩容/許韋晟) 的語言學家。
請針對使用者的輸入進行分析，特別注意「對齊」格式。

【分析原則】
1. **第一行**：顯示原始句子。
2. **中間表格 (核心分析)**：
   - 請將句子拆解為單詞，製作成一個 **Markdown 表格**。
   - **表格第一列**：填入「基底形式」(還原詞根與詞綴，如 rmngaw -> r<m>engag)。
   - **表格第二列**：填入「語法標註」(嚴格使用書中術語：主事焦點、受事焦點、主格、屬格、斜格等，不可用英文縮寫)。
   - 確保每一個詞彙直向對齊。
3. **第四行**：翻譯區，請固定留空填寫 "(請在此輸入中文翻譯)"。

【標註規則參考】
- **焦點**：主事(m-, -m-, me-), 受事(-un), 處所(-an), 工具/受惠(s-, se-)。
- **時貌**：未來(mp-, emp-, meha), 完成(wada, <n>), 進行(gisu, gaga)。
- **代名詞**：=ku(我.主格), =su(你.主格), =mu(我.屬格), =na(他.屬格), knan(我.斜格)。
- **特殊詞**：ka(主格標記), o(主題標記), ni(連接詞), hug(疑問助詞)。

【輸出格式範例】
### 第一行：原始句子
Mkla su rmngaw kari Truku hug?

### 詞法分析表 (第二、三行對齊)
| me-kela=su | r<m>engag | kari | Truku | hug |
| :--- | :--- | :--- | :--- | :--- |
| 主事焦點-會=你.主格 | <主事焦點>說 | 話 | 太魯閣 | 助詞 |

### 第四行：中文翻譯
(請在此輸入中文翻譯)
"""

# 分析按鈕
if st.button("開始標註分析", type="primary"):
    if not api_key:
        st.error("請先在左側輸入 Google API Key！")
    elif not truku_input:
        st.warning("請輸入句子！")
    else:
        # --- 3. 初始化 Google Gemini ---
        try:
            genai.configure(api_key=api_key)
            MODEL_VERSION = 'gemini-2.0-flash-001'
            model = genai.GenerativeModel(MODEL_VERSION)
        except Exception as e:
            st.error(f"模型初始化失敗: {e}")
            st.stop()
        
        # --- 開始生成內容 ---
        try:
            with st.spinner(f'正在使用 {MODEL_VERSION} 進行結構對齊分析...'):
                # 使用三個引號 f""" 來包住，避免斷行錯誤
                full_prompt = f"""{grammar_rules}

使用者輸入句子：{truku_input}
請依照範例格式輸出："""
                
                response = model.generate_content(full_prompt)
                result = response.text

            # 顯示結果
            st.markdown(result)
            
            st.success("分析完成！表格已自動對齊。")

        except Exception as e:
            st.error(f"生成過程中發生錯誤：{str(e)}")
            st.info("請檢查您的 API Key 是否正確，或是模型額度是否足夠。")

# 頁尾
st.markdown("---")
st.caption("規則依據：原住民族委員會《太魯閣語語法概論》 | Powered by Google Gemini")
