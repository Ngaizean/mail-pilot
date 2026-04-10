{{ recipient }} 你好，

今天是 {{ date }}，以下是今日提醒：

{% for item in items %}
  {{ loop.index }}. {{ item }}
{% endfor %}

祝好，
{{ sender }}
