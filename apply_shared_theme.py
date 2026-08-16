from pathlib import Path
import re

ROOT = Path(__file__).parent
PAGES = sorted(p for p in ROOT.glob('*.html') if not p.name.startswith('admin'))

AR_FOOTER = '''
<footer class="site-footer">
    <div class="footer-content">
        <div class="footer-section">
            <h3>الصفحات القانونية</h3>
            <ul>
                <li><a href="#">سياسة الخصوصية</a></li>
                <li><a href="#">الشروط والأحكام</a></li>
                <li><a href="#">إخلاء المسؤولية</a></li>
                <li><a href="#">الأمان وحماية العميل</a></li>
            </ul>
        </div>
        <div class="footer-section">
            <h3>خدمة العملاء والاتصال</h3>
            <p><strong>خدمة العملاء:</strong> 19900</p>
            <p><strong>الخط الأرضي:</strong> 0223456789</p>
            <p><strong>البريد الإلكتروني الرسمي:</strong> info@nbk.com</p>
        </div>
    </div>
    <div class="footer-bottom"><p>جميع الحقوق محفوظة © البنك الأهلي 2026</p></div>
</footer>'''

EN_FOOTER = '''
<footer class="site-footer">
    <div class="footer-content">
        <div class="footer-section">
            <h3>Legal Pages</h3>
            <ul>
                <li><a href="#">Privacy Policy</a></li>
                <li><a href="#">Terms &amp; Conditions</a></li>
                <li><a href="#">Disclaimer</a></li>
                <li><a href="#">Customer Security</a></li>
            </ul>
        </div>
        <div class="footer-section">
            <h3>Customer Care &amp; Contact</h3>
            <p><strong>Customer Care:</strong> 19900</p>
            <p><strong>Landline:</strong> 0223456789</p>
            <p><strong>Official Email:</strong> info@nbk.com</p>
        </div>
    </div>
    <div class="footer-bottom"><p>All rights reserved © National Bank Egypt 2026</p></div>
</footer>'''


def header(is_en: bool) -> str:
    login = 'login_en.html' if is_en else 'login.html'
    language = 'index.html' if is_en else 'index_en.html'
    label = 'العربية' if is_en else 'English'
    alt = 'National Bank Egypt' if is_en else 'البنك الأهلي'
    menu = 'Menu' if is_en else 'القائمة'
    brand = 'National Bank Egypt' if is_en else 'البنك الأهلي المصري'
    login_label = 'Login' if is_en else 'تسجيل الدخول'
    return f'''\n<header class="site-header">\n    <a class="site-brand" href="{'index_en.html' if is_en else 'index.html'}" aria-label="{alt}">\n        <img src="static_nbe_logo.png" alt="{alt}">\n        <span class="brand-name">{brand}</span>\n    </a>\n    <div class="site-header-actions header-left">\n        <a href="{login}" class="login-btn">{login_label}</a>\n        <a href="{language}" class="lang-btn">{label}</a>\n        <div class="header-icon" title="{menu}" aria-label="{menu}">&#9776;</div>\n    </div>\n</header>'''

for path in PAGES:
    text = path.read_text(encoding='utf-8')
    is_en = path.name.endswith('_en.html')

    if 'shared-theme.css' not in text:
        text = text.replace('</head>', '    <link rel="stylesheet" href="shared-theme.css">\n</head>', 1)

    new_header = header(is_en)
    text, header_count = re.subn(r'\s*<header\b[^>]*>.*?</header>', new_header, text, count=1, flags=re.S | re.I)
    if header_count == 0:
        text = text.replace('<body>', '<body>' + new_header, 1)

    new_footer = EN_FOOTER if is_en else AR_FOOTER
    text, footer_count = re.subn(r'\s*<footer\b[^>]*>.*?</footer>', new_footer, text, count=1, flags=re.S | re.I)
    if footer_count == 0:
        text = text.replace('</body>', new_footer + '\n</body>', 1)

    path.write_text(text, encoding='utf-8')
    print(path.name, 'header=', header_count or 1, 'footer=', footer_count or 1)
