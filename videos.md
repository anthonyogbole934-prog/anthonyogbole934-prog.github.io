---
layout: default
title: Videos
permalink: /videos/
---
<div class="wrap">
<h2 class="section-title">Videos</h2>
{% assign vids = site.posts | where_exp: "p", "p.youtube" %}
{% if vids.size == 0 %}
<p class="empty">🎬 Videos are coming soon. Subscribe to our YouTube channel so you don't miss them!</p>
{% else %}
<div class="grid">
{% for post in vids %}
<a class="card" href="{{ post.url | relative_url }}">
<div class="thumb"><img src="https://i.ytimg.com/vi/{{ post.youtube }}/hqdefault.jpg" alt="{{ post.title | escape }}" loading="lazy"><span class="play">▶ Video</span></div>
<div class="card-body"><h3>{{ post.title }}</h3></div></a>
{% endfor %}
</div>
{% endif %}
</div>
