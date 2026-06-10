# 前端对话流布局重构 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将手机壳卡片式联调页重构为全屏对话流布局，统一三种 agent 内嵌卡片风格

**Architecture:** 纯 CSS 重构，不改变 JS 逻辑和 HTML 模板结构。两阶段页面状态（欢迎态/对话态）通过 CSS class 切换控制。消息流使用 flexbox 纵向排列，卡片统一继承基类样式。

**Tech Stack:** HTML + CSS + Vanilla JS（无框架，现有技术栈不变）

**Spec:** `docs/superpowers/specs/2026-06-09-frontend-chat-layout-design.md`

**Files:**
- Modify: `.worktrees/location-agent/app/playground/distributor_chat/index.html`

---

### Task 1: 修复上轮 sed 误伤的 CSS contamination

- [ ] **Step 1: 回退 .messages 的 display: grid contamination**

`.messages` 当前被改成了 `display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr))`，恢复为 flex 纵向排列。

```css
.messages {
  padding: 14px 18px 18px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
```

- [ ] **Step 2: 回退 .message 的 display: grid contamination**

```css
.message {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-width: 92%;
}
```

- [ ] **Step 3: 确认 .card-field-list 多列 grid 保留**

行 286-291 的多列 grid 是有意为之，确认保留。

---

### Task 2: 重构为全屏对话流布局

- [ ] **Step 1: 修改 body 为全屏 flex 容器**

```css
body {
  margin: 0;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(circle at top right, rgba(36, 107, 255, 0.08), transparent 24%),
    linear-gradient(180deg, #eff4ff 0%, var(--bg) 38%, #f7f9fc 100%);
  color: var(--ink);
  font-family: "IBM Plex Sans", "PingFang SC", "Hiragino Sans GB", "Noto Sans SC", sans-serif;
}
```

- [ ] **Step 2: 替换 .page / .phone-shell 为全屏结构**

删除旧样式，新增全屏布局容器。

- [ ] **Step 3: 欢迎态 Hero**

欢迎态垂直居中，对话开始后隐藏 (`body.chat-active .welcome-hero { display: none }`)。

```css
.welcome-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: 40px 20px;
  text-align: center;
}
body.chat-active .welcome-hero { display: none; }
```

- [ ] **Step 4: 对话态顶栏**

对话开始后显示在顶部 (`body.chat-active .chat-topbar { display: flex }`)。

```css
.chat-topbar {
  display: none;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  background: #fff;
  border-bottom: 1px solid var(--line);
  flex-shrink: 0;
}
body.chat-active .chat-topbar { display: flex; }
```

- [ ] **Step 5: 消息流区域**

```css
.chat-messages-wrap {
  display: none;
  flex: 1;
  overflow-y: auto;
}
body.chat-active .chat-messages-wrap {
  display: flex;
  flex-direction: column;
}
.messages {
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 800px;
  width: 100%;
  margin: 0 auto;
}
```

- [ ] **Step 6: 底部语音栏固定**

```css
.voice-bar {
  flex-shrink: 0;
  padding: 12px 20px calc(12px + env(safe-area-inset-bottom));
  background: #fff;
  border-top: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
```

- [ ] **Step 7: 重写 HTML 结构**

移除 `.page > .phone-shell` 包裹，改为 body 直接包含：welcome-hero → chat-topbar → chat-messages-wrap → voice-bar。

- [ ] **Step 8: JS 切换逻辑**

首条消息成功后 `document.body.classList.add("chat-active")`，`resetSession()` 时移除。

---

### Task 3: 统一三种卡片样式

- [ ] **Step 1: 统一 .agent-inline-card 基类**

```css
.agent-inline-card {
  width: 100%;
  max-width: 720px;
  align-self: flex-start;
  background: #fff;
  border: 1px solid #dde6f7;
  border-radius: 24px;
  padding: 18px;
  box-shadow: 0 10px 24px rgba(17, 24, 39, 0.06);
}
```

- [ ] **Step 2: 统一控件样式（select/input/textarea + focus 态）**

```css
.enum-action-card select,
.company-action-card select,
.company-action-card input,
.location-action-card select,
.location-action-card textarea {
  width: 100%;
  padding: 12px 14px;
  border: 1px solid #cfdbf1;
  border-radius: 16px;
  font: inherit;
  font-size: 14px;
  background: #fbfdff;
  color: var(--ink);
  transition: border-color 0.2s;
}
...:focus {
  outline: none;
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(36, 107, 255, 0.1);
}
```

- [ ] **Step 3: 统一候选列表 hover 效果**

```css
.candidate-item:hover {
  border-color: var(--brand);
  background: #eef4ff;
}
```

---

### Task 4: 验证

- [ ] **Step 1: 重新部署并确认布局**

```bash
docker compose -f docker-compose.location-agent.yml up -d --force-recreate app
```
打开 `http://127.0.0.1:8010/playground/distributor-agent` 确认欢迎态和对话态切换正常。

- [ ] **Step 2: 测试三种卡片渲染**

枚举卡片、公司卡片、位置卡片均正确渲染。

- [ ] **Step 3: 跑 playground 测试**

```bash
docker compose -f docker-compose.location-agent.yml exec app python -m pytest tests/test_playground.py -v
```
