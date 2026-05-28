# IVX 智能研发实时看板（中文说明）

English documentation: see [README.md](README.md).

![ivx dashboard home](assets/demo.png)

## 项目介绍
中文名称：`IVX 智能研发实时看板`。

`ivx Dashboard` 是一个独立运行的实时研发看板，用于把 AI 驱动交付过程中的关键运行状态集中展示在一个界面中。

## 看板内容
- 项目进度与阶段任务
- CI 与测试质量状态
- 协作者运行状态与人工介入信号
- 最近事件与风险变化

## 典型使用方式
- 启动服务并打开看板
- 在界面中选择或切换项目
- 持续跟踪健康度、风险和阻塞项
- 根据介入队列安排处理动作

## 主要组成
- 运行服务：`server.py`
- 应用入口：`app.py`
- Web 页面：`web/index.html`
- 本地数据：`data/live_progress.json`、`data/dashboard_state.json`

## 安装
1. 通过 PyPI 安装：
   - `pip install ivx`
2. 安装固定版本：
   - `pip install "ivx==<version>"`
3. 从源码安装：
   - `pip install "git+https://github.com/rendao/ivx.git@main"`

## 安装后如何使用
1. 查看可用命令：
   - `ivx --help`
2. 启动服务：
   - `ivx serve --host 127.0.0.1 --port 8789`
3. 打开看板：
   - `http://127.0.0.1:8789`
4. 在界面中配置项目：
   - 点击顶部 Project 按钮
   - 填写项目名称和路径后保存

## 快速开始
1. 启动服务：
   - `python app.py --host 127.0.0.1 --port 8789`
2. 打开看板：
   - `http://127.0.0.1:8789`
3. 在界面中完成项目设置：
   - 点击顶部 Project 按钮
   - 填写项目名称/路径后保存
   - 需要重新初始化时可勾选 Force re-bootstrap
