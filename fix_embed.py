import sys
path = r"C:\Users\K\Herd\outreach\embed.js"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

idx = text.find(";(function(){const e=document.currentScript")
if idx == -1:
    print("Could not find the target string.")
    sys.exit(1)

new_code = """;(function(){
    const c = window.VUE_CHATBOT_CONFIG;
    if (!c) { console.error("No VUE_CHATBOT_CONFIG found"); return; }
    const d = document.createElement("div");
    d.id = "my-dynamically-created-chatbot-widget-container";
    document.body.appendChild(d);
    nc({render:()=>bo(Tc,{
        chatbot: c.chatbotData,
        customisation: c.customisationData,
        themeConfig: c.themeConfigData,
        fastapiUrl: c.fastapiUrl
    })}).mount("#" + d.id);
})();"""

with open(path, "w", encoding="utf-8") as f:
    f.write(text[:idx] + new_code)

print("Successfully updated embed.js")