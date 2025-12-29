I'm sorry for not offering an English ver of this document but it's just too much work for me.
If you want to read in English, use a translator.


此文档是MAICA-MTTS后端API接口的使用文档, 编纂版本为v1.0.


MAICA-MTTS的通信只包含短连接, 因为流式传输意义不大, 处理也过于复杂.

* 短连接的地址是 https://maicadev.monika.love/tts (官方服务), 自行部署则是 http://localhost:7000 .

> 若无特别说明, 此后的内容均以官方服务为例. 自行部署情况请参考后端部署文档, 自行推广.  
> MAICA-MTTS的后端结构相对简单, 基本上只是MAICA的延申. MAICA的相关设计与概念请参见MAICA后端文档.


# 短连接的使用:

## 基本介绍:

短连接是MAICA-MTTS的唯一连接方式, 其兼顾生成与一些MAICA自有功能的实现.

## 输入和输出:

见MAICA文档.

## 可用端点:

### 生成TTS:

> 端点: GET `/generate`

* 需要access_token, content

    其中content为json格式的生成内容:

    `{"text": "待生成语音的文本", "emotion": "表情", "target_lang": "zh", "persistence": 是否缓存, "lossless": 是否无损}`

    * 其中text的长度建议控制在一到数个自然句内, 以控制表现.

    * emotion: 可使用MAICA的标准表情, 如"微笑". 具体见源码.
    > emotion能起到的作用是有限的, 并不总能生成准确的语气. 设为与实际句子相符的值以改善表现.

    * target_lang: 目标语言, 可选"zh"或"en".

    * persistence: 设为true会在服务端缓存, 仅各客户端间通用的条目应启用此功能(如不含[player]等字段). 默认true.

    * lossless: 设为true会返回wav, 否则返回mp3. 默认false.
    > 传输wav文件会产生高额流量开销, 发布版客户端不可使用.

若请求成功, 端点仅返回对应的音频文件. 否则端点正常返回json.

### 在线执行验证:

> 端点: GET `/legality`

见MAICA文档.

### 在线加密令牌:

> 端点: GET `/register`

见MAICA文档.

### 获取服务器声明表:

> 端点: GET `/servers`

见MAICA文档.

### 获取后端服务状态:

> 端点: GET `/accessibility`

见MAICA文档.

### 获取版本信息:

> 端点: GET `/version`

见MAICA文档.

> 应当注意, MAICA-MTTS的前端名称与MAICA不同, 故范例形如:  
> `{"curr_version": "后端当前版本", "legc_version": "兼容的最旧版本", "fe_synbrace_version": "Synbrace前端的可用最旧版本"`

### 获取模型负载:

> 端点: GET `/workload`

见MAICA文档.