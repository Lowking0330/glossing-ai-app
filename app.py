import streamlit as st
import google.generativeai as genai
import os

# --- 1. 頁面設定 ---
st.set_page_config(page_title="太魯閣語語法標註助手", page_icon="🏔️", layout="wide")

st.title("🏔️ 太魯閣語自動語法標註系統")
st.markdown("依據**《太魯閣語語法概論》**體系進行分析，並透過 AI 自動生成對齊表格。")

# --- 2. 側邊欄設定 (固定模型版本) ---
with st.sidebar:
    st.header("⚙️ 設定")
    
    # 優先嘗試從 Streamlit Secrets 讀取 API Key (方便開發者)
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("🔑 已讀取系統內建 API Key")
    else:
        api_key = st.text_input("輸入 Google AI API Key", type="password")
        st.markdown("[如何取得 Google API Key?](https://aistudio.google.com/app/apikey)")
    
    st.info("🤖 目前模型：Fixed (gemini-2.0-flash-001)")

# --- 3. 定義語法規則 System Prompt (優化版) ---
# 為了確保「對齊」，最強制的方式是要求輸出 Markdown Table
grammar_rules = """
你是一位專精於《太魯閣語語法概論》(2018, 李佩容/許韋晟) 的語言學家。
請針對使用者的輸入進行分析，並嚴格按照以下格式輸出。

【輸出格式要求】
請將句子拆解，輸出為一個標準的 Markdown 表格 (Table)。
表格必須包含以下四欄：
1. **原詞**：原始輸入的單詞。
2. **基底形式**：還原詞根與詞綴 (例如: rmngaw -> r<m>engag)。
3. **語法標註**：請使用中文全稱 (如：主事焦點、受事焦點、主格、屬格、斜格、連接詞、疑問助詞)。
4. **中文翻譯**：該單詞的對應意思。

表格下方，請提供整句流暢的中文翻譯。

【標註規則參考】
- 焦點：主事(m-, -m-, me-), 受事(-un), 處所(-an), 工具/受惠(s-, se-)。
- 時貌：未來(mp-, emp-, meha), 完成(wada, <n>), 進行(gisu, gaga)。
- 代名詞：=ku(我.主格), =su(你.主格), =mu(我.屬格), =na(他.屬格), knan(我.斜格)。
- 特殊詞：ka(主格標記), o(主題標記), ni(連接詞), hug(疑問助詞)。
"""

# --- 4. 主輸入區 ---
truku_input = st.text_area("請輸入太魯閣語句子：", height=100, placeholder="例如：Mkla su rmngaw kari Truku hug?")

# --- 5. 執行按鈕與邏輯 ---
if st.button("🚀 開始標註分析", type="primary"):
    if not api_key:
        st.error("❌ 請先在左側輸入 Google API Key！")
    elif not truku_input:
        st.warning("⚠️ 請輸入句子！")
    else:
        # 設定模型參數 (固定 gemini-2.0-flash-001)
        MODEL_ID = 'gemini-2.0-flash-001'
        
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(MODEL_ID)
            
            with st.spinner(f'正在呼叫 {MODEL_ID} 進行結構對齊分析...'):
                full_prompt = f"{grammar_rules}\n\n使用者輸入句子：{truku_input}\n請輸出分析結果："
                
                # 發送請求
                response = model.generate_content(full_prompt)
                result = response.text

            # 顯示結果
            st.markdown("### 📊 分析結果")
            st.markdown(result)
            st.success("分析完成！")

        except Exception as e:
            # 針對 404 錯誤 (模型名稱錯誤) 做特別提示
            error_msg = str(e)
            st.error(f"❌ 發生錯誤：{error_msg}")
            
            if "404" in error_msg:
                st.warning(
                    f"⚠️ 找不到模型 `{MODEL_ID}`。\n\n"
                    "可能原因：\n"
                    "1. 您的 API Key 沒有權限存取此模型。\n"
                    "2. Google 更改了模型名稱 (例如變成 `gemini-2.0-flash-exp`)。\n"
                    "3. 請嘗試更新套件：`pip install -U google-generativeai`"
                )
            elif "400" in error_msg:
                 st.warning("⚠️ API Key 無效，請檢查您的金鑰。")

# --- 6. 頁尾 ---
st.markdown("---")
st.caption("規則依據：原住民族委員會《太魯閣語語法概論》 | Powered by Google Gemini")
