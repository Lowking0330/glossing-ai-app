import streamlit as st
import google.generativeai as genai
import json

# 設定網頁標題與介面
st.set_page_config(page_title="太魯閣語語法標註助手", page_icon="🏔️", layout="wide")

st.title("🏔️ 太魯閣語自動語法標註系統")
st.markdown("依據**《太魯閣語語法概論》**體系進行分析，採用無框線對齊排版。")

# 側邊欄：設定 API Key
with st.sidebar:
    st.header("設定")
    api_key = st.text_input("輸入 Google AI API Key", type="password")
    st.markdown("[如何取得 Google API Key?](https://aistudio.google.com/app/apikey)")
    st.info("本工具使用 Gemini-1.5-Flash (JSON Mode)。")

# 主輸入區
truku_input = st.text_area("請輸入太魯閣語句子：", height=100, placeholder="例如：Mkla su rmngaw kari Truku hug?")

# --- 定義 JSON 格式的 System Prompt ---
# 我們要求 AI 輸出 JSON，這樣我們才能自由控制排版，不受 Markdown 表格限制
grammar_rules = """
你是一位專精於《太魯閣語語法概論》(2018, 李佩容/許韋晟) 的語言學家。
請針對使用者的輸入進行分析。

【分析原則】
1. **基底形式 (base)**：還原詞根與詞綴 (如 mkla -> me-kela)。
2. **語法標註 (gloss)**：嚴格使用書中術語 (主事焦點、受事焦點、主格、屬格等)。
3. **翻譯 (translation)**：固定留空。

【輸出格式】
請務必輸出標準的 **JSON 格式**，不要包含 markdown 標記 (如 ```json)：
{
  "words": [
    {"base": "me-kela=su", "gloss": "主事焦點-會=你.主格"},
    {"base": "r<m>engag", "gloss": "<主事焦點>說"}
  ],
  "translation": "(請在此輸入中文翻譯)"
}
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
            # 使用 1.5 Flash 並開啟 JSON 模式，保證格式絕對正確
            model = genai.GenerativeModel('gemini-1.5-flash', generation_config={"response_mime_type": "application/json"})
        except Exception as e:
            st.error(f"模型初始化失敗: {e}")
            st.stop()
        
        # --- 開始生成內容 ---
        try:
            with st.spinner('正在進行結構分析...'):
                full_prompt = f"""{grammar_rules}

使用者輸入句子：{truku_input}"""
                
                response = model.generate_content(full_prompt)
                
                # 解析 JSON 資料
                result_json = json.loads(response.text)

            # --- 4. 渲染漂亮的排版 (HTML/CSS) ---
            
            # 第一行：原始句子
            st.subheader("分析結果")
            st.markdown(f"**第一行：** {truku_input}")
            
            # 第二、三行：動態對齊區塊
            # 這裡使用 Flexbox 排版，讓每一個「單字+標註」成為一個群組，自動排列
            html_content = """
            <style>
                .gloss-container {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 15px; /* 單字之間的間距 */
                    margin-bottom: 20px;
                    font-family: sans-serif;
                }
                .gloss-item {
                    display: flex;
                    flex-direction: column;
                }
                .gloss-base {
                    font-weight: bold;
                    margin-bottom: 4px; /* 上下行之間的微小間距 */
                    font-size: 1rem;    /* 字體大小跟第一行一致 */
                }
                .gloss-label {
                    color: #555;
                    font-size: 1rem;    /* 字體大小跟第一行一致 */
                }
            </style>
            <div class="gloss-container">
            """
            
            # 迴圈加入每個單字
            for item in result_json["words"]:
                html_content += f"""
                <div class="gloss-item">
                    <div class="gloss-base">{item['base']}</div>
                    <div class="gloss-label">{item['gloss']}</div>
                </div>
                """
            
            html_content += "</div>"
            
            # 顯示 HTML
            st.markdown(html_content, unsafe_allow_html=True)
            
            # 第四行：翻譯
            st.markdown(f"**第四行：** {result_json['translation']}")
            
            st.success("分析完成！")

        except Exception as e:
            st.error(f"發生錯誤：{str(e)}")
            st.info("請檢查您的 API Key 是否正確。")

# 頁尾
st.markdown("---")
st.caption("規則依據：原住民族委員會《太魯閣語語法概論》 | Powered by Google Gemini")
