import time
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
opts = Options(); opts.add_argument("-headless"); opts.binary_location = "/snap/firefox/current/usr/lib/firefox/firefox"
drv = webdriver.Firefox(options=opts, service=Service("/snap/bin/geckodriver")); drv.set_window_size(1440, 900)
try:
    drv.get("http://localhost:8080"); time.sleep(2)
    print(drv.execute_script("""
      const out = {};
      out.sheets = Array.from(document.styleSheets).map(s => (s.href||'inline').replace(location.origin,''));
      let found = []; let total = 0;
      for (const s of document.styleSheets) { try { for (const r of s.cssRules) { total++; if (r.selectorText && /chat-mode|chat-topbar|^\\.tab-content \\{?$/.test(r.selectorText)) found.push(r.selectorText + ' => ' + r.style.cssText.slice(0,80)); } } catch(e) { found.push('ERR ' + e.message); } }
      out.total = total; out.found = found;
      const home = document.getElementById('home'); const sc = document.getElementById('mainSearchContainer');
      out.homeMatches = home.matches('.home-layout:not(.chat-mode)');
      out.scMatches = sc.matches('.home-layout:not(.chat-mode) .search-container');
      out.scOrder = getComputedStyle(sc).order; out.homeOverflow = getComputedStyle(home).overflowY;
      out.ffVersion = navigator.userAgent;
      return JSON.stringify(out, null, 1);
    """))
    css = drv.execute_script("return fetch('/static/css/style.css').then(r => r.text()).then(t => [t.length, t.includes('order: 1; margin-top: 0'), t.slice(0,60)])")
    print("fetched css:", css)
finally:
    drv.quit()
