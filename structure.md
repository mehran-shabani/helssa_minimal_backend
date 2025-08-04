# Medogram — Repository Blueprint

## stracture

**Version 1.5 · 02 Aug 2025**

> **Append‑Only File.** Every addition or modification **must** be recorded in `agent.log`.

---

## 1 · High‑Level Directory Tree

```
<repo‑root>/                # Django monorepo root
├─ certificate/            # medico‑legal certificates app
├─ doctor_online/          # real‑time on‑call doctors app
├─ down/                   # download routes front‑end app
├─ medagent/               # LangChain chatbot & patient docs
├─ medogram/               # core Django project package
├─ sub/                    # subscriptions & billing app
├─ telemedicine/           # wallet, visits, auth, blog, APK, orders
├─ alternative/            # ⚠️  READ‑ONLY — do not touch
├─ templates/              # shared Jinja/Django templates
│
├─ .github/                # issue templates, PR template, workflows
│   ├─ ISSUE_TEMPLATE/
│   │   ├─ bug_report.yml
│   │   └─ feature_request.yml
│   ├─ pull_request_template.md
│   └─ dependabot.yml
│
│
│               
│       
│       
│       
│
├─ tests/                  # unit / integration / e2e (≥ 90 % coverage)
│   ├─ unit/
│   ├─ integration/
│   └─ e2e/
│
├─ manage.py               # Django entry‑point
├─ pytest.ini              # pytest configuration
├─ requirements.txt        # Python dependencies
├─ Dockerfile              # root‑level Docker (fallback)
├─ .dockerignore
├─ .gitignore
└─ README.md               # overview & quick‑start
```

---

## 2 · Folder Responsibilities

| Path                       | Purpose                                                        |
| -------------------------- | -------------------------------------------------------------- |
| **certificate/**           | Medico‑legal certificate workflows                             |
| **doctor\_online/**        | Display on‑call doctors in real time                           |
| **down/**                  | Customer download routes                                       |
| **medagent/**              | LangChain chatbot & patient document storage                   |
| **medogram/**              | Core Django project (settings, URLs, wsgi/asgi)                |
| **sub/**                   | Subscription and billing logic                                 |
| **telemedicine/**          | Wallet, visit booking, authentication, blog, APK links, orders |
| **alternative/**           | **Read‑only sandbox — absolutely no edits**                    |
| **templates/**             | Shared HTML / Jinja / Django templates                         |
| **infrastructure/docker/** | Containerisation & orchestration artefacts                     |
| **.github/**               | Issue templates, PR template, Dependabot, workflows            |

---

## 3 · Maintenance Checklist

1. Ensure every path listed in §1 exists and matches its described purpose.
2. Create any missing files/folders **exactly** as shown.
3. Update outdated templates or Docker artefacts when necessary.
4. **Never** modify the `alternative/` folder.
5. Record each action in `agent.log`.

---

## 4 · Pre‑Commit Gate

Before committing, confirm that:

-

---

*End of specification — further changes only via logged proposals.*

