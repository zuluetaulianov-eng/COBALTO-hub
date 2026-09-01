<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:output method="html" encoding="UTF-8" indent="yes"/>
<xsl:template match="/">
<html lang="es">
<head>
    <meta charset="UTF-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    <title><xsl:value-of select="rss/channel/title"/> — Feed RSS</title>
    <link rel="preconnect" href="https://fonts.googleapis.com"/>
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous"/>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&amp;family=Outfit:wght@600;800;900&amp;display=swap" rel="stylesheet"/>
    <style>
        :root {
            --bg: #07090e;
            --card-bg: rgba(15, 23, 42, 0.85);
            --primary: #00E5FF;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --border: rgba(0, 229, 255, 0.2);
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background-color: var(--bg);
            color: var(--text-main);
            font-family: 'Inter', sans-serif;
            line-height: 1.6;
            padding: 2rem 1rem;
        }
        .container {
            max-width: 860px;
            margin: 0 auto;
        }
        .header {
            background: rgba(15, 23, 42, 0.95);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 10px 30px rgba(0, 229, 255, 0.1);
            backdrop-filter: blur(10px);
        }
        .header-top {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1rem;
        }
        .logo {
            width: 50px;
            height: 50px;
            border-radius: 10px;
            border: 2px solid var(--primary);
            object-fit: cover;
        }
        .title {
            font-family: 'Outfit', sans-serif;
            font-size: 1.8rem;
            font-weight: 800;
            color: var(--primary);
        }
        .desc {
            color: var(--text-muted);
            font-size: 0.95rem;
            margin-bottom: 1rem;
        }
        .info-box {
            background: rgba(0, 229, 255, 0.05);
            border-left: 3px solid var(--primary);
            padding: 0.8rem 1rem;
            border-radius: 0 8px 8px 0;
            font-size: 0.85rem;
            color: var(--text-muted);
        }
        .info-box a {
            color: var(--primary);
            text-decoration: none;
            font-weight: 600;
        }
        .feed-list {
            display: flex;
            flex-direction: column;
            gap: 1.2rem;
        }
        .item-card {
            background: var(--card-bg);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 14px;
            padding: 1.5rem;
            transition: transform 0.2s, border-color 0.2s;
        }
        .item-card:hover {
            border-color: var(--primary);
            transform: translateY(-2px);
        }
        .item-meta {
            display: flex;
            align-items: center;
            gap: 0.8rem;
            font-size: 0.8rem;
            margin-bottom: 0.6rem;
            flex-wrap: wrap;
        }
        .badge {
            background: rgba(0, 229, 255, 0.15);
            color: var(--primary);
            padding: 3px 10px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 0.75rem;
            border: 1px solid rgba(0, 229, 255, 0.3);
        }
        .date {
            color: var(--text-muted);
        }
        .item-title {
            font-family: 'Outfit', sans-serif;
            font-size: 1.3rem;
            font-weight: 700;
            margin-bottom: 0.6rem;
        }
        .item-title a {
            color: #fff;
            text-decoration: none;
            transition: color 0.2s;
        }
        .item-title a:hover {
            color: var(--primary);
        }
        .item-desc {
            color: var(--text-muted);
            font-size: 0.92rem;
            margin-bottom: 1rem;
        }
        .btn-read {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: var(--primary);
            color: #000;
            font-weight: 700;
            font-size: 0.82rem;
            padding: 8px 16px;
            border-radius: 8px;
            text-decoration: none;
            transition: opacity 0.2s;
        }
        .btn-read:hover {
            opacity: 0.9;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-top">
                <img src="/static/img/vn_logo.png" alt="Logo" class="logo"/>
                <div>
                    <h1 class="title"><xsl:value-of select="rss/channel/title"/></h1>
                    <p class="desc"><xsl:value-of select="rss/channel/description"/></p>
                </div>
            </div>
            <div class="info-box">
                📡 <strong>Feed RSS 2.0 Oficial:</strong> Puedes suscribir esta URL a cualquier lector de noticias (Feedly, Inoreader, Apple News). 
                <a href="/noticias">Ir al Portal Web Principal →</a>
            </div>
        </div>
        
        <div class="feed-list">
            <xsl:for-each select="rss/channel/item">
                <div class="item-card">
                    <div class="item-meta">
                        <span class="badge"><xsl:value-of select="category"/></span>
                        <span class="date">📅 <xsl:value-of select="pubDate"/></span>
                    </div>
                    <h2 class="item-title">
                        <a href="{link}" target="_blank"><xsl:value-of select="title"/></a>
                    </h2>
                    <p class="item-desc"><xsl:value-of select="description"/></p>
                    <a href="{link}" target="_blank" class="btn-read">Leer Noticia Completa ➔</a>
                </div>
            </xsl:for-each>
        </div>
    </div>
</body>
</html>
</xsl:template>
</xsl:stylesheet>
