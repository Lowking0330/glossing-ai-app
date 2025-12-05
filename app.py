import streamlit as st
import google.generativeai as genai
import os

# 1. 設定網頁標題與介面 (Layout 設為 wide 以容納寬表格)
st.set_page_config(page_title="太魯閣語語法標註助手", page_icon="🏔️", layout="wide")

st.title("🏔️ 太魯閣語自動語法標註系統")
st.markdown("依據**《太魯閣語語法概論》**體系進行分析，透過 AI 生成對齊表格。")

# 2. 側邊欄設定
with st.sidebar:
    st.header("⚙️ 設定")
    
    # 優先嘗試從 st.secrets 讀取 key (方便開發者)，如果沒有則顯示輸入框
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("已從 Secrets 讀取 API Key")
    else:
        api_key = st.text_input("輸入 Google AI API Key", type="password")
        st.markdown("[如何取得 Google API Key?](https://aistudio.google.com/app/apikey)")

    # 模型選擇器 (增加穩定性)
    model_version = st.selectbox(
        "選擇模型版本",
        ["gemini-2.0-flash-exp", "gemini-1.5-flash", "gemini-1.5-pro"],
        index=0,
        help="2.0 Flash 速度快但為預覽版；若失敗請嘗試 1.5 Flash。"
    )
    
    st.divider()
    with st.expander("查看語法規則 Prompt"):
        st.info("此工具僅供參考，語言分析結果可能需人工校對。")

# 3. 定義語法規則 System Prompt (優化版：強制 Markdown 表格)
# 改為「垂直表格」邏輯，比橫向對齊更適合 RWD 網頁閱讀
grammar_rules = """
你是一位專精於《太魯閣語語法概論》(2018, 李佩容/許韋晟) 的語言學家。
請將使用者的輸入句子拆解，並製作成一個標準的 Markdown 表格。

【輸出格式要求】
請直接輸出一個 Markdown 表格，包含以下四個欄位：
1. **原句單詞**：原始輸入的單詞。
2. **基底形式**：還原詞根與詞綴 (例如: rmngaw -> r<m>engag)。
3. **語法標註**：(焦點、時貌、格位) 請使用中文全稱，如：主事焦點、受事焦點、主格、屬格。
4. **中文對應**：該單詞的中文意義。

最後，在表格下方，請提供整句的流暢中文翻譯。

【標註參考庫】
- 焦點：主事(m-, -m-, me-), 受事(-un), 處所(-an), 工具/受惠(s-, se-)。
- 時貌：未來(mp-, emp-, meha), 完成(wada, <n>), 進行(gisu, gaga)。
- 代名詞：=ku(我.主格), =su(你.主格), =mu(我.屬格), =na(他.屬格), knan(我.斜格)。
- 特殊詞：ka(主格標記), o(主題標記), ni(連接詞), hug(疑問助詞)。
"""

# 4. 主輸入區
col1, col2 = st.columns([2, 1])
with col1:
    truku_input = st.text_area("請輸入太魯閣語句子：", height=150, placeholder="例如：Mkla su rmngaw kari Truku hug?")

with col2:
    st.write("### 操作說明")
    st.markdown("""
    1. 輸入太魯閣語句子。
    2. 點擊按鈕進行分析。
    3. AI 將自動拆解詞彙並標註語法。
    """)
    analyze_btn = st.button("🚀 開始標註分析", type="primary", use_container_width=True)

# 5. 執行邏輯
if analyze_btn:
    if not api_key:
        st.error("❌ 請先在左側輸入 Google API Key！")
    elif not truku_input:
        st.warning("⚠️ 請輸入句子！")
    else:
        try:
            # 設定 API
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_version)
            
            with st.spinner(f'正在使用 {model_version} 進行語言學分析...'):
                # 組合 Prompt
                full_prompt = f"{grammar_rules}\n\n---\n使用者輸入句子：{truku_input}\n\n請輸出 Markdown 表格："
                
                # 呼叫模型
                response = model.generate_content(full_prompt)
                result = response.text

            # 6. 顯示結果
            st.markdown("### 📊 分析結果")
            st.markdown(result)
            
            # 提供複製功能的提示 (Streamlit markdown 表格選取即可複製)
            st.caption("您可以直接選取上方表格內容複製到 Excel 或 Word 中。")

        except Exception as e:
            st.error("🚫 發生錯誤")
            st.error(f"錯誤訊息: {str(e)}")
            st.markdown("""
            **排查建議：**
            1. 檢查 API Key 是否正確。
            2. 若使用 Gemini 2.0 失敗，請嘗試切換至 1.5 Flash。
            3. 確認 `google-generativeai` 套件版本是否已更新。
            """)

# 頁尾
st.divider()
st.caption("規則依據：原住民族委員會《太魯閣語語法概論》 | Powered by Google Gemini")
