import time
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
opts = Options(); opts.add_argument("-headless"); opts.binary_location = "/snap/firefox/current/usr/lib/firefox/firefox"
drv = webdriver.Firefox(options=opts, service=Service("/snap/bin/geckodriver")); drv.set_window_size(1440, 900)
try:
    drv.get("http://localhost:8080"); time.sleep(2)
    js = """
    const out = {};
    for (const sel of ['#chatHeader', '#mainSearchContainer', '#statStrip', '#suggestionsBox', '#chatMessages', '.chat-topbar']) {
      const el = document.querySelector(sel); if (!el) { out[sel] = 'MISSING'; continue; }
      const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
      out[sel] = {top: Math.round(r.top), bottom: Math.round(r.bottom), h: Math.round(r.height), display: cs.display, order: cs.order, mt: cs.marginTop};
    }
    const home = document.getElementById('home'); const cs = getComputedStyle(home);
    out['#home'] = {display: cs.display, flexDirection: cs.flexDirection, h: home.clientHeight, scrollH: home.scrollHeight, cls: home.className};
    out['innerHeight'] = innerHeight;
    return JSON.stringify(out);
    """
    print("LANDING:", drv.execute_script(js))
    drv.execute_script("""
      const home = document.getElementById('home'); home.classList.add('chat-mode');
      document.getElementById('chatHeader').classList.add('minimized'); document.getElementById('suggestionsBox').classList.add('hidden');
      const m = document.getElementById('chatMessages'); m.classList.remove('hidden');
      m.innerHTML = '<div class="message user"><div class="msg-avatar"></div><div class="msg-content">Q</div></div>' + '<div class="message ai"><div class="msg-avatar"></div><div class="msg-content">' + 'line<br>'.repeat(120) + '<div class="sources-container">end</div></div></div>';
    """); time.sleep(0.5)
    print("CHAT:", drv.execute_script(js))
    print("SCROLLERS before:", drv.execute_script("return JSON.stringify({doc: [document.scrollingElement.scrollTop, document.scrollingElement.scrollHeight, innerHeight], app: [document.querySelector('.app-container').scrollTop, document.querySelector('.app-container').scrollHeight, document.querySelector('.app-container').clientHeight], main: [document.querySelector('.main-content').scrollTop, document.querySelector('.main-content').scrollHeight, document.querySelector('.main-content').clientHeight], home: [document.getElementById('home').scrollTop, document.getElementById('home').scrollHeight, document.getElementById('home').clientHeight], msgs: [document.getElementById('chatMessages').scrollTop, document.getElementById('chatMessages').scrollHeight, document.getElementById('chatMessages').clientHeight]})"))
    drv.execute_script("document.querySelector('.sources-container').scrollIntoView()"); time.sleep(0.3)
    print("SCROLLERS after scrollIntoView:", drv.execute_script("return JSON.stringify({doc: document.scrollingElement.scrollTop, app: document.querySelector('.app-container').scrollTop, main: document.querySelector('.main-content').scrollTop, home: document.getElementById('home').scrollTop, msgs: document.getElementById('chatMessages').scrollTop, topbar: document.querySelector('.chat-topbar').getBoundingClientRect().top})"))
finally:
    drv.quit()
