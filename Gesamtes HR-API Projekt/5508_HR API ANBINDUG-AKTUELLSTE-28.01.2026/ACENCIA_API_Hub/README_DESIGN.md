# ACENCIA Design System Documentation

## 1. Overview

This document outlines the design system created for the ACENCIA Hub application. The goal of this system is to provide a modern, clean, and consistent user interface that is easy to maintain and extend. The entire system is built on a foundation of design tokens and reusable components.

For a live demonstration of all components and tokens, please run the application and visit the `/styleguide` route.

## 2. Design Tokens

Design tokens are the core of the system, stored as CSS variables in `acencia_hub/static/css/tokens.css`. They ensure consistency across the entire application. **Never use hardcoded values for colors, fonts, or spacing in component styles. Always use a token.**

### Key Token Categories:
-   **Colors (`--color-*`)**: Includes the primary brand palette, an accent palette for calls-to-action, and a full neutral (gray) scale for text, backgrounds, and borders.
-   **Typography (`--font-*`)**: Defines font families (`--font-display` for headings, `--font-body` for everything else), weights, and line heights.
-   **Spacing (`--space-*`)**: A numeric scale (1-10) for all margins, paddings, and gaps.
-   **Radius (`--radius-*`)**: Defines border-radius values for components.
-   **Shadows (`--shadow-*`)**: Pre-defined box-shadows for elevating elements.

## 3. Theming (Dark/Light Mode)

The application supports both a light (default) and dark theme.
-   The theme is toggled using the switch in the header.
-   The current theme is stored in `sessionStorage` and persists for the user's session.
-   The mechanism is powered by a `data-theme="dark"` attribute on the `<body>` tag.
-   Dark theme color variables are defined within a `[data-theme="dark"]` block in `tokens.css`.

When creating new components, ensure they work in both light and dark modes. Most components will adapt automatically if they use the semantic color tokens (e.g., `--color-bg-surface`, `--color-text-primary`). For components that need specific dark-mode styles, add them to `style.css` under a `[data-theme="dark"]` selector.

## 4. Component-Based CSS

The application's styles are organized by component in `acencia_hub/static/css/style.css`. When adding or modifying a component, please keep its styles grouped under the relevant comment block (e.g., `/* --- Cards --- */`).

### Core Components:
-   **Buttons**: `.button`, `.button-primary`, `.button-secondary`, `.button-danger`.
-   **Cards**: `.card`, with child elements `.card-header`, `.card-body`, `.card-footer`.
-   **Forms**: Standard form elements are styled globally. Use `.form-group` for layout.
-   **Tables**: Use the `.table` class for data tables.
-   **Tabs**: Use the `.tab-container` and associated classes for tabbed navigation.
-   **Badges**: `.badge` for small status indicators.

## 5. How to Extend the UI

1.  **Check the Styleguide**: Before creating a new component, check the `/styleguide` page to see if an existing component can be used or adapted.
2.  **Use Tokens**: Always build new styles using the existing design tokens from `tokens.css`.
3.  **Create Reusable Components**: If a new UI element is needed, structure its CSS in a reusable, component-based way in `style.css`.
4.  **Test in Both Themes**: Ensure the new component looks and functions correctly in both light and dark modes.
5.  **Update the Styleguide**: If you create a significant new component, add it to the `styleguide.html` template so it's documented for others.
