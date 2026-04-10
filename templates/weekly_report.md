{{ recipient }}，

以下是 {{ date }} 的工作周报：

## 本周完成

{{ summary | default("（请在 --var summary=... 中填写）") }}

## 下周计划

{{ plan | default("（请在 --var plan=... 中填写）") }}

---

发送自 Mail Pilot ({{ account_alias }})
