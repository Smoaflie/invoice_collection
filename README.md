<p align="center">
  <img src="static/images/logo.png" alt="Logo" width="80" height="80">
  <h3 align="center">发票收集工具</h3>
  <p align="center">
    一个围绕着飞书多维表格平台，对发票进行汇总统计管理的工具。
    <br />
    <br />
    <a href="https://github.com/Smoaflie/invoice_collection/issues">报告Bug</a>
    ·
    <a href="https://github.com/Smoaflie/invoice_collection/issues">提出新特性</a>
  </p>

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![MIT License][license-shield]][license-url]
[![LinkedIn][linkedin-shield]][linkedin-url]

## 目录

- [功能展示](#功能展示)
- [上手指南](#上手指南)
  - [开发前的配置要求](#开发前的配置要求)
  - [安装步骤](#安装步骤)
- [文件目录说明](#文件目录说明)
- [部署](#部署)
- [依赖模块](#依赖模块)
- [作者](#作者)
- [鸣谢](#鸣谢)
- [版权说明](#版权说明)

### 功能展示

- 用户批量上传发票，脚本自动解析发票，提取发票信息并同步结果到收集表内

- 允许使用多个收集表收集不同时期发票

- 自动去重

- 自定义发票审批规则

  <img src=".\static\images\show1.jpg" alt="image-20250615125741251" style="zoom:33%;" />

  <img src=".\static\images\custom_rule.png" alt="image-20250615125741251" style="zoom: 50%;" />

- 创建发票信息云文档 / 同步全部发票信息到云文档

- 自定义发票标签（允许批量修改发票标签）
  <img src=".\static\images\show2.png" alt="image-20250615125741251" style="zoom:50%;" />

- 按不同的规则导出发票（允许多种规则并存，文件采用硬链接，不占据额外存储空间）

  - 注意：Windows系统中，仅NTFS的磁盘格式才支持硬链接
  
  <img src=".\static\images\export.png" alt="image-20250615125741251" style="zoom:50%;" />
  
- 自定义导出规则

  <img src=".\static\images\custom_rule2.png" alt="image-20250615125741251" style="zoom:50%;" />

  

### 上手指南

###### 开发前的要求

1. Python 3.8+
2. [百度智能云账号](https://ai.baidu.com/ai-doc/OCR/fk3h7xu7h)(用以调用OCR接口，每月1000次免费额度)
3. [飞书自建应用](https://open.feishu.cn/document/develop-process/self-built-application-development-process)(脚本通过应用身份操作飞书多维表格)

###### **安装步骤**

1. 克隆该仓库

    ```bash
    git clone https://github.com/Smoaflie/invoice_collection.git
    cd invoice_collection
    ```

2. 配置python虚拟环境(可选)

   ```bash
   python3 -m venv .venv
   
   # windows系统
   .\.venv\Scripts\activate
   # Linux系统
   source .venv/bin/activate
   ```

3. 安装依赖模块

   ```bash
   pip install -r requirements.txt
   ```

4. 配置环境变量（分别获取飞书API 百度API凭证信息）

   ```
   nano .env.example
   # 按照提示信息填入必要参数
   # ...
   mv .env.example .env
   ```

5. 在飞书中导入该项目的[多维表格模板](https://fa4g5no1b1f.feishu.cn/wiki/HXZzwy1r8ijs7ykA1yDctUdonQd?from=from_copylink)

6. 将你的自建应用添加为文档应用

   > <img src=".\static\images\add_document_app1.png" alt="add_document_app1" style="zoom: 25%;" /><img src=".\static\images\add_document_app2.png" alt="add_document_app2" style="zoom: 25%;" />

7. 到 [飞书开发者后台](https://open.feishu.cn/app) 添加如下权限(可批量添加)

   ```json
   {
     "scopes": {
       "tenant": [
         "bitable:app",
         "contact:user.base:readonly"
       ],
       "user": [
         "bitable:app",
         "contact:user.base:readonly"
       ]
     }
   }
   ```

8. 执行

   ```bash
   python3 main.py --help
   ```

**参数解释**：

> - lark bitable url: 飞书多维表格链接
>
>   格式: 
>
>   - 如果多维表格的 URL 以 **feishu.cn/base** 开头，该多维表格的 app_token 是下图高亮部分：![app_token.png](/static/images/app_token.png)
>   - 如果多维表格的 URL 以 **feishu.cn/wiki** 开头，你需调用知识库相关[获取知识空间节点信息](https://open.feishu.cn/document/ukTMukTMukTM/uUDN04SN0QjL1QDN/wiki-v2/space/get_node)接口获取多维表格的 app_token。当 obj_type 的值为 bitable 时，obj_token 字段的值才是多维表格的 app_token。
>
>   以 **feishu.cn/base** 开头的url获取办法:
>
>   ![lark_bitable_url](/static/images/lark_bitable_url.png)



### 文件目录说明

```
invoice_collect/
├── core/                      # 📦 核心模块（发票与底层逻辑）
│   ├── invoice/               # 发票处理逻辑（基类、OCR 等）
│   │   ├── base.py            # 发票基类（如 InvoiceBase）
│   │   ├── baidu_ocr.py       # Baidu OCR 识别接口封装
│   │   └── __init__.py
│   ├── log.py                 # 日志配置模块
│   ├── utils.py               # 通用工具函数
│   └── __init__.py
├── static/                    # 📁 README 用到的静态资源（如图片）
│   └── images
├── main.py                    # ✅ 入口程序（含参数解析、调度等）
├── function.py                # 核心功能函数
├── custom_rule.py             # 自定义规则逻辑
├── .env.example               # 环境变量样例
├── group.json.example         # group 配置样例
├── README.md                  # 项目说明文档
└── requirements.txt           # 依赖清单

```


### 依赖模块

- [oapi-sdk-python](https://github.com/larksuite/oapi-sdk-python)
- [sqlite-utils](https://github.com/simonw/sqlite-utils)
- [sqlite-web](https://github.com/coleifer/sqlite-web)
- [tqdm](https://github.com/tqdm/tqdm)
- [yaspin](https://github.com/pavdmyt/yaspin)

### 作者

[@smoaflie](https://github.com/Smoaflie)

mail: smoaflie@outlook.com

qq: 1373987167  

### 鸣谢

- [Best_README_template](https://github.com/shaojintian/Best_README_template)


- [Img Shields](https://shields.io)
- [Choose an Open Source License](https://choosealicense.com)

### 版权说明

该项目签署了MIT 授权许可，详情请参阅 [LICENSE](https://github.com/Smoaflie/invoice_collection/blob/master/LICENSE)



<!-- links -->

[contributors-shield]: https://img.shields.io/github/contributors/Smoaflie/invoice_collection.svg?style=flat-square
[contributors-url]: https://github.com/Smoaflie/invoice_collection/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/Smoaflie/invoice_collection.svg?style=flat-square
[forks-url]: https://github.com/Smoaflie/invoice_collection/network/members
[stars-shield]: https://img.shields.io/github/stars/Smoaflie/invoice_collection.svg?style=flat-square
[stars-url]: https://github.com/Smoaflie/invoice_collection/stargazers
[issues-shield]: https://img.shields.io/github/issues/Smoaflie/invoice_collection.svg?style=flat-square
[issues-url]: https://img.shields.io/github/issues/Smoaflie/invoice_collection.svg
[license-shield]: https://img.shields.io/github/license/Smoaflie/invoice_collection.svg?style=flat-square
[license-url]: https://github.com/Smoaflie/invoice_collection/blob/master/LICENSE.txt
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=flat-square&logo=linkedin&colorB=555
[linkedin-url]: https://linkedin.com/in/shaojintian



