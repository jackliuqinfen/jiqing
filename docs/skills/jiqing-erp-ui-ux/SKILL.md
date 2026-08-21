---
name: jiqing-erp-ui-ux
description: Use when designing, reviewing, or implementing UI and UX in the Jiqing construction-management ERP. Keep the experience lifecycle-first, task-oriented, truthful about data, and consistent with the existing workbench shell.
---

# Jiqing ERP UI/UX

Use this skill for product screens, workbench navigation, project-management views, settlement views, settings, empty states, and interaction reviews in this repository.

## Product experience

- Design for a real engineering-management ERP, not a showcase dashboard.
- Organize each screen around the current lifecycle stage, current task, owner, missing materials, settlement conditions, anomalies, and the next action.
- Keep the protected lifecycle and core business fields intact. Use constrained configuration instead of fully free-form workflow or table behavior.
- When real records are absent, show an honest empty state. Do not invent projects, amounts, progress, risks, or financial totals.
- AI may extract and suggest; people confirm important amounts, payment terms, documents, and lifecycle changes.

## Application shell

The current shell has four layers:

1. Top platform navigation for 工作台、招投标、项目管理、审计、资料、结算.
2. A context-sensitive left sidebar for the active module's views and actions.
3. Workspace tabs with back/forward, pin, close, restore, and reorder behavior.
4. The main content area with a page header, command toolbar, business surface, and recoverable state panels.

Preserve these boundaries. Do not add a second competing navigation system inside a module, and do not put system configuration, low-value status, or duplicate module links into a project view sidebar.

The sidebar may be full, icon-only, or hidden. Keep collapse, resize, hover expansion, keyboard focus, and mobile horizontal navigation usable. The user avatar/name opens 个人设置; administrator-only system rules and user management stay under 后台管理.

## Visual language

- Use the light blue-to-white workspace atmosphere already defined by \`src/styles/arco-premium-workbench.css\`.
- Keep navigation and query chrome light/translucent; keep tables, forms, records, and high-density business content on solid white surfaces.
- Use the dynamic theme tokens from \`src/ui/theme.ts\`; default primary blue is \`#165DFF\`, with blue-gray text, pale blue active surfaces, cyan for active progress, amber for attention, and red only for danger.
- Prefer restrained borders, small radii, clear hierarchy, and shallow shadows. Glass effects are for shell/chrome, not every business component.
- Use Chinese business labels in the interface. Never expose internal enum names when a user-facing status exists.

## Screen patterns

- Start with \`PageHeader\`: title, one-sentence purpose, useful metadata, and only the actions relevant to the current role.
- Keep one primary toolbar. For project ledgers, use progressive filtering: search, filter entry, sort, query/reset; move advanced status/manager filters into the filter panel.
- Show saved views, grouping, layout switching, and column configuration as secondary controls. Do not repeat a second filter/action toolbar inside the table or card body.
- When rows are selected, replace the idle utility row with a contextual batch-action row. Do not show grey disabled bulk actions in the idle state.
- The project ledger supports information table, compact table, and project-card layouts. These are different information densities, not cosmetic title changes.
- Clicking a project continues into the existing project-detail modal and its tabs for overview, documents, audit, settlement, variations, and logs. Do not create a competing drawer or second project-detail interaction.
- Use \`StatePanel\` or an equivalent component for loading, empty, error, and informational states. Every error state should explain recovery and offer a safe next action when possible.
- Keep settlement terminology plain: distinguish 甲方付款情况 from 款项到账情况, and show why a project cannot proceed.

## Accessibility and interaction review

Check at minimum:

- visible focus for custom buttons, tabs, filter triggers, password toggles, and sidebar controls;
- labels and \`aria-current\`/\`aria-selected\` for navigation and tabs;
- keyboard access to search, filters, selection mode, modal tabs, and primary actions;
- readable contrast on pale backgrounds and status tags;
- responsive behavior at narrow widths without hiding the next action;
- loading, no-data, error, permission-denied, and unavailable-device states;
- no misleading success, progress, or financial data when the backend has returned nothing.

## Source files

Read only the files relevant to the requested surface, starting with:

- \`src/views/AppLayout.vue\`
- \`src/styles/arco-premium-workbench.css\`
- \`src/ui/theme.ts\`
- \`src/components/StatePanel.vue\`
- the target view under \`src/views/\`
- \`Jiqing-ERP-Memory/01-长期规划/工程管理ERP长期规划.md\`
- \`Jiqing-ERP-Memory/02-产品决策/决策索引.md\`
