---
name: jiqing-login-page
description: Use when designing, reviewing, or implementing the Jiqing ERP login page and authentication entry experience. Preserve the separate brand-led login visual, internal-account boundary, clear errors, and responsive form behavior.
---

# Jiqing ERP Login Page

Use this skill for \`src/views/LoginView.vue\`, login copy, authentication-entry UX, password interaction, account-opening guidance, or login-page visual review.

## Current design

- The login page is intentionally separate from the logged-in workbench background.
- The desktop composition is a two-column layout: brand/utility narrative on the left and a focused account card on the right.
- The left side uses the construction logo, \`JIQING CONSTRUCTION\`, the title 工程管理系统, the line 项目协同、资料归档、审计流转, and three capability chips: 项目、资料、审计.
- The page uses a pale blue-gray asset plus a blue-white gradient and subtle diagonal line overlay. Keep the background quiet enough for the form to remain the strongest action surface.
- The form card uses a translucent white surface, soft border, 18px desktop radius, large shadow, and restrained blue primary accents. Do not turn the login page into the denser workbench chrome.

## Form and states

- Default to the 登录 tab. Keep the 注册 tab only as an account-opening explanation: accounts are opened by an administrator; do not imply self-service registration if it is not enabled.
- Use vertical labels for 账号 and 密码, large controls, username/password autocomplete, clearable username input, and a password show/hide control with an explicit accessible label.
- Keep the primary action as 登录系统 and make loading disable duplicate submissions.
- Normalize errors into user-understandable messages: invalid credentials, locked account, unavailable service, or a safe generic fallback. Do not expose raw server errors, enum names, or implementation details.
- Keep 无法登录？ as a recovery/help affordance, not as an unimplemented password-reset promise.
- After successful authentication, the current flow shows a short welcome transition with the user's display name and then redirects to the requested route or the workbench. Preserve the redirect behavior and do not add an unbounded animation.

## Authentication boundaries

- The entry point is for existing internal accounts. Never auto-create an internal account from an external identity or QR scan.
- If WeChat QR login is added, bind it under 个人设置, keep AppSecret and tokens server-side, and match only an existing internal account that is already bound. An unbound user should be directed to an administrator.
- Personal profile, password, and device preferences belong in 个人设置. User roles, enablement, binding status, and system rules belong in 后台管理.
- Never place plaintext passwords or access tokens in browser storage, the renderer, project memory, or this skill.

## Responsive behavior

- At about 920px, collapse the two-column composition to one column and reduce the brand scale.
- At about 640px, use a narrow page gutter, smaller title/card spacing, allow vertical scrolling, and hide the decorative capability chips.
- Keep the form, error message, password toggle, focus ring, and primary action visible and usable on a short viewport.

## Review checklist

- Brand and form hierarchy are obvious within one glance.
- The login action is the only dominant action.
- Registration copy does not promise self-service account creation.
- Error, loading, locked-account, and unavailable-service states are clear and non-technical.
- Password visibility, keyboard focus, tab semantics, labels, and contrast are accessible.
- Login background remains independent from administrator-configurable workbench background.
- Browser visual acceptance is separate from source-code inspection; do not claim visual acceptance without a fresh captured screen.

## Source files

- \`src/views/LoginView.vue\`
- \`src/assets/login-page-bg-grey.jpg\`
- \`src/assets/aoqiang-construction-logo.svg\`
- \`src/store/auth.ts\`
- \`src/router/index.ts\`
- \`Jiqing-ERP-Memory/02-产品决策/2026-07-16-工作台背景与管理员配置边界.md\`
- \`Jiqing-ERP-Memory/02-产品决策/2026-07-29-个人设置与后台管理职责边界.md\`
