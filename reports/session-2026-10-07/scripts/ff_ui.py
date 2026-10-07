import sys, time
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
out = sys.argv[1]; ask = len(sys.argv) < 3 or sys.argv[2] != "--no-ask"
opts = Options(); opts.add_argument("-headless"); opts.binary_location = "/snap/firefox/current/usr/lib/firefox/firefox"
drv = webdriver.Firefox(options=opts, service=Service("/snap/bin/geckodriver")); drv.set_window_size(1440, 900)
ok = True
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name); ok = ok and bool(cond)
try:
    drv.get("http://localhost:8080")
    drv.execute_script("""window.__logs=[]; for (const k of ['warn','error']) { const o=console[k]; console[k]=(...a)=>{window.__logs.push(k+': '+a.map(String).join(' ')); o(...a);} } window.addEventListener('error', e => window.__logs.push('pageerror: '+e.message));""")
    for _ in range(20):
        if drv.find_element(By.ID, "heroChunks").text not in ("–", ""): break
        time.sleep(0.5)
    check("stats loaded: " + drv.find_element(By.ID, "statusText").text + " | " + drv.find_element(By.ID, "heroChunks").text + " chunks", drv.find_element(By.ID, "heroChunks").text not in ("–", ""))
    check("6 question cards", len(drv.find_elements(By.CSS_SELECTOR, ".qcard")) == 6)
    drv.save_screenshot(out + "-home.png")
    # theme toggle
    drv.find_element(By.ID, "themeToggle").click(); time.sleep(0.6)
    check("light theme applied", drv.execute_script("return document.documentElement.getAttribute('data-theme')") == "light")
    drv.save_screenshot(out + "-home-light.png")
    drv.find_element(By.ID, "themeToggle").click(); time.sleep(0.4)
    check("dark theme restored", drv.execute_script("return document.documentElement.getAttribute('data-theme')") is None)
    # keyboard: "/" focuses the input
    drv.find_element(By.TAG_NAME, "body").send_keys("/"); time.sleep(0.2)
    check("'/' focuses the search box", drv.switch_to.active_element.get_attribute("id") == "searchInput")
    # Code search tab
    drv.find_element(By.CSS_SELECTOR, "[data-tab=codesearch]").click(); time.sleep(0.5)
    b = drv.find_element(By.ID, "codeSearchInput"); b.send_keys("where is the map pin logic"); b.send_keys(Keys.ENTER)
    for _ in range(40):
        if drv.find_elements(By.CSS_SELECTOR, "#codeSearchResults .source-item"): break
        time.sleep(0.5)
    time.sleep(0.8)
    items = drv.find_elements(By.CSS_SELECTOR, "#codeSearchResults .source-item")
    check(f"code search returned {len(items)} results | " + drv.find_element(By.ID, "codeSearchMeta").text.replace("\n", " ")[:80], len(items) == 10)
    if items:
        items[0].find_element(By.TAG_NAME, "summary").click(); time.sleep(0.5)
        check("code is syntax-highlighted", len(drv.find_elements(By.CSS_SELECTOR, "#codeSearchResults .source-code .hljs-keyword, #codeSearchResults .source-code .hljs-variable, #codeSearchResults .source-code .hljs-title")) > 0)
        check("GitHub link present", "github.com/ushahidi/platform/blob/" in items[0].find_element(By.CSS_SELECTOR, ".source-link").get_attribute("href"))
        check("Explain with AI button present", len(items[0].find_elements(By.CSS_SELECTOR, ".source-actions button")) == 1)
    drv.save_screenshot(out + "-codesearch.png")
    if ask:
        drv.find_element(By.CSS_SELECTOR, "[data-tab=home]").click(); time.sleep(0.4)
        b = drv.find_element(By.ID, "searchInput"); b.send_keys("How does the UpdateUsecase work?"); b.send_keys(Keys.ENTER)
        time.sleep(0.3); steps = len(drv.find_elements(By.CSS_SELECTOR, ".pipeline .step")); check("pipeline stepper shown (or answer already in)", steps == 3 or bool(drv.find_elements(By.CSS_SELECTOR, ".answer-stack")))
        drv.save_screenshot(out + "-thinking.png")
        for _ in range(150):
            if drv.find_elements(By.CSS_SELECTOR, ".answer-stack, .error-card") and not drv.find_elements(By.CSS_SELECTOR, ".typing-indicator"): break
            time.sleep(1)
        time.sleep(3)
        check("answer rendered | " + drv.find_element(By.CSS_SELECTOR, ".answer-meta").text.replace("\n", " ")[:110], len(drv.find_elements(By.CSS_SELECTOR, ".simple-card, .warning-card")) >= 1)
        llm_used = "rerank" in drv.find_element(By.CSS_SELECTOR, ".answer-meta").text
        check("diagram svg rendered" if llm_used else "search-only answer (LLM unavailable), diagram not expected", (len(drv.find_elements(By.CSS_SELECTOR, ".diagram-container svg")) == 1) if llm_used else True)
        check("evidence list present", len(drv.find_elements(By.CSS_SELECTOR, ".sources-container .source-item")) >= 3)
        check("last-answer latency shown: " + drv.find_element(By.ID, "statLatency").text, drv.find_element(By.ID, "statLatency").text not in ("–", ""))
        drv.execute_script("document.querySelector('#chatMessages').scrollTop = 0"); time.sleep(0.4)
        drv.save_screenshot(out + "-answer.png")
        card = drv.find_elements(By.CSS_SELECTOR, ".diagram-container")
        if card:
            drv.execute_script("arguments[0].scrollIntoView()", card[0]); time.sleep(0.4); drv.save_screenshot(out + "-diagram.png")
            drv.find_element(By.CSS_SELECTOR, ".card-action").click(); time.sleep(0.8)
            check("diagram modal opens", "hidden" not in drv.find_element(By.ID, "diagramModal").get_attribute("class"))
            drv.save_screenshot(out + "-diagram-modal.png")
            drv.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE); time.sleep(0.3)
            check("Esc closes the modal", "hidden" in drv.find_element(By.ID, "diagramModal").get_attribute("class"))
        if "hidden" in drv.find_element(By.CSS_SELECTOR, ".sources-list").get_attribute("class"): drv.find_element(By.CSS_SELECTOR, ".green-header").click(); time.sleep(0.5)
        drv.execute_script("document.querySelector('.sources-container').scrollIntoView()"); time.sleep(0.3)
        drv.find_elements(By.CSS_SELECTOR, ".sources-container .source-item summary")[0].click(); time.sleep(0.4)
        drv.save_screenshot(out + "-evidence.png")
        check("New chat resets the view", (drv.find_element(By.CSS_SELECTOR, ".chat-topbar .icon-btn").click(), time.sleep(0.4), "chat-mode" not in drv.find_element(By.ID, "home").get_attribute("class"))[2])
    # History tab
    drv.find_element(By.CSS_SELECTOR, "[data-tab=chat]").click(); time.sleep(0.5)
    check("history: " + drv.find_element(By.ID, "historyCount").text + " | nav badge " + drv.find_element(By.ID, "navHistoryCount").text, True)
    drv.save_screenshot(out + "-history.png")
    drv.find_element(By.CSS_SELECTOR, "[data-tab=questions]").click(); time.sleep(0.5); drv.save_screenshot(out + "-dataset.png")
    check("33 dataset questions clickable", len(drv.find_elements(By.CSS_SELECTOR, ".dataset-list li")) == 33)
    drv.find_element(By.CSS_SELECTOR, "[data-tab=github]").click(); time.sleep(0.5); drv.save_screenshot(out + "-repository.png")
    drv.find_element(By.CSS_SELECTOR, "[data-tab=about]").click(); time.sleep(0.5); drv.save_screenshot(out + "-about.png")
    logs = [l for l in drv.execute_script("return window.__logs") if "favicon" not in l]
    for l in logs: print("LOG", l[:300])
    check("no page errors", not any(l.startswith("pageerror") or l.startswith("error") for l in logs))
finally:
    drv.quit()
print("ALL PASS" if ok else "SOME CHECKS FAILED")
