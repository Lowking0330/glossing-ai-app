import streamlit as st
import google.generativeai as genai

# 設定網頁標題與介面
st.set_page_config(page_title="太魯閣語語法標註助手 (Gemini版)", page_icon="🏔️")

st.title("🏔️ 太魯閣語自動語法標註系統")
st.markdown("依據**《太魯閣語語法概論》**體系進行四行分析。")

# 側邊欄：設定 API Key
with st.sidebar:
    st.header("設定")
    api_key = st.text_input("輸入 Google AI API Key", type="password")
    st.markdown("[如何取得 Google API Key?](https://aistudio.google.com/app/apikey)")
    st.info("本工具使用 Gemini-1.5-Flash 模型。")

# 主輸入區
truku_input = st.text_area("請輸入太魯閣語句子：", height=100, placeholder="例如：Mkla su rmngaw kari Truku hug?")

# 定義依據《太魯閣語語法概論》的系統提示詞 (System Prompt)
# 這裡我們將書中的規則"灌輸"給 AI
grammar_rules = """
你是一位專精於《太魯閣語語法概論》(2018, 李佩容/許韋晟) 的語言學家。
請針對使用者的輸入進行「四行分析」。

【分析原則】
1. **第二行 (基底形式)**：必須還原詞根與詞綴。
   - 例如：mkla -> me-kela, rmngaw -> r<m>engag (g在字尾弱化為w), empquyux -> emp-quyux。
2. **第三行 (語法標註)**：必須嚴格使用該書的術語，不可使用英文縮寫(如AF, Gen)。
   - **焦點系統** [參照書中表6.1]：
     - 主事焦點 (標記: m-, -m-, -um-, me-, mg-, ∅)
     - 受事焦點 (標記: -un)
     - 處所焦點 (標記: -an)
     - 工具焦點/受惠焦點 (標記: s-, se-)
   - **時貌系統** [參照書中表6.2]：
     - 未來/非實現：mp-, emp-, meha
     - 完成/實現：wada, <n>, <mn>, <en>
     - 進行：gisu, gaga
   - **格位標記** [參照書中5.1節]：
     - ka：主格
     - ni：連接詞
     - o：主題標記
   - **代名詞** [參照書中表5.1]：
     - =ku (我.主格), =su (你.主格)
     - =mu (我.屬格), =na (他.屬格)
     - knan (我.斜格), sunan (你.斜格)
3. **第四行**：必須留空，固定填寫 "(請在此輸入中文翻譯)"。

【輸出格式範例】
第一行：Mkla su rmngaw kari Truku hug?
第二行：me-kela=su r<m>engag kari truku hug
第三行：主事焦點-會/知道=你.主格 <主事焦點>說 話/語言 太魯閣 助詞
第四行：(請在此輸入中文翻譯)
"""

# 分析按鈕
if st.button("開始標註分析", type="primary"):
    if not api_key:
        st.error("請先在左側輸入 Google API Key！")
    elif not truku_input:
        st.warning("請輸入句子！")
    else:
        try:
            # 設定 Google Gemini
            genai.configure(api_key="AIzaSyBZKeQqqYvKfV6y4igQExIjOxN-U_mA8eM")
            
            # 使用 gemini-3.0-flash，速度快且對指令遵循度高
            model = genai.GenerativeModel('gemini-3.0-flash')
            
            with st.spinner('正在調閱《太魯閣語語法概論》規則進行分析...'):
                # 組合 Prompt
                full_prompt = f"{grammar_rules}\n\n使用者輸入句子：{truku_input}\n請提供四行分析："
                
                response = model.generate_content(full_prompt)
                result = response.text

            # 顯示結果
            st.subheader("分析結果")
            st.code(result, language="text")
            
            st.success("分析完成！")

        except Exception as e:
            st.error(f"發生錯誤：{str(e)}")
            st.info("請檢查您的 API Key 是否正確。")

# 頁尾
st.markdown("---")

st.caption("規則依據：原住民族委員會《太魯閣語語法概論》 | Powered by Google Gemini")

