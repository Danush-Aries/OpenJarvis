"""Jarvis Skill Registry — 53 expert-level skills across 12 domains.

Each skill is a structured knowledge module that Jarvis can activate
to bring specialized expertise into any conversation. Skills are loaded
by the SkillManager and injected into the system prompt when activated.
"""

from __future__ import annotations

from typing import Dict, List

from openjarvis.skills_expert.types import Skill, SkillCategory, SkillLevel

# ---------------------------------------------------------------------------
# Master registry of all skills
# ---------------------------------------------------------------------------

_SKILLS: Dict[str, Skill] = {}


def _reg(skill: Skill) -> Skill:
    """Register a skill in the global registry."""
    _SKILLS[skill.id] = skill
    return skill


def get_all_skills() -> List[Skill]:
    """Return all registered skills."""
    return list(_SKILLS.values())


def get_skill(skill_id: str) -> Skill | None:
    """Look up a skill by ID."""
    return _SKILLS.get(skill_id)


def get_skills_by_category(category: SkillCategory) -> List[Skill]:
    """Return all skills in a given category."""
    return [s for s in _SKILLS.values() if s.category == category]


def search_skills(query: str) -> List[Skill]:
    """Search skills by keyword across name, description, and triggers."""
    q = query.lower()
    results = []
    for s in _SKILLS.values():
        if (q in s.name.lower()
                or q in s.description.lower()
                or q in s.id.lower()
                or any(q in kw.lower() for kw in s.trigger_keywords)):
            results.append(s)
    return results


def count_skills() -> int:
    """Return the total number of registered skills."""
    return len(_SKILLS)


# =========================================================================
# == WEB DEVELOPMENT (7) =================================================
# =========================================================================

_reg(Skill(
    id="react-nextjs",
    name="React & Next.js",
    description="React 19, Next.js 15 — server components, RSC, App Router, Suspense, streaming SSR, and the full React ecosystem",
    category=SkillCategory.WEB_DEV,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["react", "nextjs", "next.js", "jsx", "server component", "rsc", "app router", "ssr", "suspense"],
    tool_requirements=["web_search", "file_read", "file_write", "shell_exec"],
    dependencies=[],
    examples=[
        "Build a Next.js 15 app with server components and streaming",
        "Migrate from Pages Router to App Router",
        "Optimize React rendering with useMemo and useCallback"
    ],
    prompt="""You are an expert in React 19 and Next.js 15. Apply these patterns:

1. **Server Components First** — Default to server components. Only use 'use client' when you need interactivity (hooks, event handlers, browser APIs).
2. **App Router** — Use the `app/` directory with file-based routing. Layouts are nested by default. Use `loading.js`, `error.js`, `not-found.js` for each route segment.
3. **Streaming & Suspense** — Wrap async components in `<Suspense>` with fallbacks. Use `loading.tsx` for automatic Suspense boundaries.
4. **Data Fetching** — Fetch directly in server components. Use `cache()` for deduplication. Never use `useEffect` for data fetching.
5. **Server Actions** — Use `\"use server\"` for mutations. Forms work without JavaScript.
6. **React 19 Features** — Use `useActionState()`, `useFormStatus()`, `useOptimistic()` for form handling. Server Components can use `async/await` directly.
7. **TypeScript** — Use strict TypeScript with type inference. Prefer `interface` over `type` for props.
8. **Performance** — Use `next/image` for images, `next/font` for fonts, `next/link` for client-side navigation. Leverage React.memo sparingly and only with measurable benefits.
9. **Styling** — Use Tailwind CSS v4 with CSS-first configuration (no tailwind.config.js needed). Use CSS Modules or CSS-in-JS (styled-components, Emotion) for component-scoped styles.
10. **Testing** — Playwright for e2e, Vitest + React Testing Library for unit/integration.
"""))

_reg(Skill(
    id="vue-nuxt",
    name="Vue 3 & Nuxt",
    description="Vue 3 Composition API, Nuxt 3, Pinia, Vite, and the Vue ecosystem",
    category=SkillCategory.WEB_DEV,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["vue", "nuxt", "vuejs", "composition api", "pinia", "vite"],
    tool_requirements=["web_search", "file_read", "file_write"],
    prompt="""You are an expert in Vue 3 and Nuxt 3. Apply these patterns:

1. **Composition API** — Always use `<script setup>` syntax. Use `ref()` for primitives, `reactive()` for objects, `computed()` for derived state.
2. **Nuxt 3 Conventions** — Use `pages/` directory for routing, `components/` for auto-imported components, `composables/` for shared logic, `server/` for API routes.
3. **Data Fetching** — Use `useFetch()` and `useAsyncData()` in Nuxt. They deduplicate requests and support SSR.
4. **State Management** — Use Pinia for global state. Define stores with the setup syntax.
5. **TypeScript** — Infer types from API responses. Use `defineProps<{}>()` for typed props.
6. **Performance** — Use `v-memo` for list optimization, `defineAsyncComponent` for code splitting, `keep-alive` for dynamic components.
"""))

_reg(Skill(
    id="tailwind-css",
    name="Tailwind CSS",
    description="Tailwind CSS v4 — utility-first CSS framework with CSS-first configuration, design tokens, responsive design, and component patterns",
    category=SkillCategory.WEB_DEV,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["tailwind", "css", "utility-first", "responsive", "design system"],
    tool_requirements=["file_write", "file_read"],
    dependencies=[],
    examples=[
        "Build a responsive dashboard layout with Tailwind",
        "Create a custom design system with Tailwind v4 CSS-first config",
        "Optimize Tailwind bundle with dynamic class detection"
    ],
    prompt="""You are a Tailwind CSS v4 expert. Apply these patterns:

1. **CSS-First Configuration** — Tailwind v4 uses `@import \"tailwindcss\";` in your main CSS file. No `tailwind.config.js` needed. Use `@theme` blocks for design tokens.
2. **Design Tokens** — Define colors, fonts, spacing in `@theme {}` blocks in your CSS file. These auto-generate utility classes.
3. **Responsive Design** — Mobile-first by default. Use `sm:`, `md:`, `lg:`, `xl:`, `2xl:` prefixes. Use `container` for centered layouts.
4. **Component Patterns** — Extract repeated utility patterns using `@apply` in CSS components, or use React/Vue component composition.
5. **Dark Mode** — Use `dark:` variant with `@media (prefers-color-scheme: dark)` or class-based toggling.
6. **Custom Variants** — Use `@variant` in CSS to create custom state variants.
7. **Performance** — Use `@layer` for organizing CSS. PurgeCSS is built-in — no config needed. Avoid dynamic class construction (concatenation) so the scanner can detect classes.
8. **Animations** — Use built-in `animate-*` utilities. Extend with `@keyframes` and `@theme` in CSS.
"""))

_reg(Skill(
    id="css-animations",
    name="CSS Animations & Effects",
    description="CSS keyframes, transitions, transforms, scroll-driven animations, view transitions, and performance-optimized motion design",
    category=SkillCategory.WEB_DEV,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["animation", "keyframe", "transition", "transform", "css animation", "motion", "scroll animation"],
    tool_requirements=["file_write", "file_read"],
    dependencies=["tailwind-css"],
    examples=[
        "Create a scroll-triggered parallax effect",
        "Build smooth page transitions with View Transitions API",
        "Design a loading skeleton animation"
    ],
    prompt="""You are a CSS animation expert. Apply these patterns:

1. **Performance** — Prefer `transform` and `opacity` animations (GPU-composited). Avoid animating `width`, `height`, `top`, `left` (triggers layout).
2. **will-change** — Use `will-change: transform, opacity` sparingly — only on elements that will animate, and remove it after.
3. **Scroll-Driven Animations** — Use `animation-timeline: scroll()` for scroll-linked animations without JavaScript. Combine with `animation-range` for start/end control.
4. **View Transitions API** — Use `document.startViewTransition()` for smooth page transitions. Use `::view-transition-old()` and `::view-transition-new()` pseudo-elements for customization.
5. **Keyframe Patterns** — Use `@keyframes` with descriptive names. Use `animation-fill-mode: forwards` to retain end state.
6. **Stagger Animations** — Use `--delay` custom properties with `calc()` in child selectors for staggered entrances.
7. **Accessibility** — Respect `prefers-reduced-motion`. Provide `animation: none` fallbacks.
8. **Easing** — Use cubic-bezier for natural motion. `cubic-bezier(0.16, 1, 0.3, 1)` for snappy exits, `cubic-bezier(0.34, 1.56, 0.64, 1)` for spring-like entrances.
"""))

_reg(Skill(
    id="responsive-design",
    name="Responsive Web Design",
    description="Mobile-first responsive layouts, CSS Grid, Flexbox, container queries, and cross-device testing",
    category=SkillCategory.WEB_DEV,
    level=SkillLevel.INTERMEDIATE,
    trigger_keywords=["responsive", "mobile-first", "flexbox", "grid", "container query", "breakpoint", "cross-device"],
    tool_requirements=["file_write", "file_read", "browser"],
    prompt="""You are a responsive design expert. Apply these patterns:

1. **Mobile-First** — Start with the mobile layout as the default, add breakpoints to enhance for larger screens.
2. **CSS Grid** — Use `grid-template-columns: repeat(auto-fill, minmax(300px, 1fr))` for responsive grids without media queries.
3. **Container Queries** — Use `@container` for component-level responsiveness. Define containment on parent, query on children.
4. **Fluid Typography** — Use `clamp(min, preferred, max)` for responsive font sizes. E.g., `font-size: clamp(1rem, 2.5vw, 1.5rem)`.
5. **Images** — Use `max-width: 100%` and `height: auto` on images. Use `<picture>` with `srcset` for art-directed responsive images.
6. **Touch Targets** — Minimum 44x44px touch targets on mobile. Use `@media (pointer: coarse)` for touch-specific styles.
7. **Testing** — Test on real devices, not just resize. Use Chrome DevTools device emulation for initial checks.
"""))

_reg(Skill(
    id="web-performance",
    name="Web Performance Optimization",
    description="Core Web Vitals, Lighthouse optimization, lazy loading, code splitting, caching strategies, and bundle optimization",
    category=SkillCategory.WEB_DEV,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["performance", "lighthouse", "core web vitals", "lcp", "cls", "inp", "lazy load", "code split", "bundle", "caching"],
    tool_requirements=["browser", "web_search", "shell_exec"],
    dependencies=["react-nextjs"],
    examples=[
        "Optimize LCP from 4s to under 1.5s",
        "Reduce bundle size by 60% with code splitting",
        "Implement predictive prefetching for instant navigation"
    ],
    prompt="""You are a web performance expert. Apply these patterns:

1. **Core Web Vitals** — Target LCP < 2.5s, INP < 200ms, CLS < 0.1. Optimize in this priority order.
2. **LCP Optimization** — Preload the LCP image with `<link rel=\"preload\">`. Use `fetchpriority=\"high\"`. Ensure the image is discoverable from HTML (not CSS/JS).
3. **INP Optimization** — Break long tasks into smaller chunks with `requestIdleCallback` or `scheduler.yield()`. Reduce main-thread work by moving to workers (Web Worker, Comlink).
4. **CLS Prevention** — Always set `width` and `height` on images and videos. Use `aspect-ratio` CSS property. Reserve space for dynamic content, ads, embeds.
5. **Code Splitting** — Use dynamic `import()` for route-based splitting. Lazy-load below-the-fold components, modals, and heavy libraries.
6. **Caching** — Implement service workers for offline support. Use Cache-Control headers effectively: `immutable` for hashed assets, `no-cache` for HTML.
7. **Images** — Use modern formats (WebP, AVIF). Use responsive `srcset` and `sizes`. Implement blur-up or LQIP placeholders.
8. **Fonts** — Use `font-display: swap` or `font-display: optional`. Self-host fonts. Subset fonts to only needed characters.
9. **Bundle Analysis** — Use `webpack-bundle-analyzer` or `@next/bundle-analyzer`. Identify and eliminate duplicate dependencies.
"""))

_reg(Skill(
    id="web-accessibility",
    name="Web Accessibility (a11y)",
    description="WCAG 2.2 compliance, ARIA patterns, keyboard navigation, screen reader support, color contrast, and inclusive design",
    category=SkillCategory.WEB_DEV,
    level=SkillLevel.INTERMEDIATE,
    trigger_keywords=["accessibility", "a11y", "wcag", "aria", "screen reader", "keyboard", "contrast", "inclusive"],
    tool_requirements=["browser", "web_search"],
    examples=[
        "Audit a page for WCAG AA compliance",
        "Fix keyboard navigation in a complex SPA",
        "Implement accessible modal dialog with focus trapping"
    ],
    prompt="""You are an accessibility expert. Apply these patterns:

1. **Semantic HTML** — Use native HTML elements first. `<nav>`, `<main>`, `<aside>`, `<button>`, `<a>` before ARIA. ARIA only when semantic HTML can't solve the problem.
2. **Keyboard Navigation** — All interactive elements must be reachable and operatable via keyboard. Use `tabindex=\"0\"` for custom interactive elements, `tabindex=\"-1\"` for programmatic focus.
3. **Focus Management** — Visible focus indicators (never `outline: none` without a replacement). Trap focus in modals. Return focus on close.
4. **ARIA Patterns** — Use ARIA roles, states, and properties correctly. `role=\"dialog\"` + `aria-modal=\"true\"` for modals. `aria-expanded` for toggles. `aria-live` regions for dynamic content.
5. **Color Contrast** — Minimum 4.5:1 for normal text, 3:1 for large text (WCAG AA). Don't rely solely on color for conveying information.
6. **Screen Readers** — Provide alt text for meaningful images. Use `aria-label` or `aria-labelledby` for elements without visible labels. Hide decorative elements with `aria-hidden=\"true\"`.
7. **Testing** — Use axe DevTools, Lighthouse a11y audit, keyboard-only testing, screen reader testing (VoiceOver, NVDA).
8. **Reduced Motion** — Respect `prefers-reduced-motion` and `prefers-color-scheme`. Provide static alternatives for animated content.
"""))


# =========================================================================
# == BACKEND & API (6) ====================================================
# =========================================================================

_reg(Skill(
    id="python-backend",
    name="Python Backend Development",
    description="FastAPI, Django, Flask — async Python APIs, Pydantic validation, SQLAlchemy, Alembic, and production patterns",
    category=SkillCategory.BACKEND,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["python", "fastapi", "django", "flask", "pydantic", "sqlalchemy", "alembic", "async python"],
    tool_requirements=["file_read", "file_write", "shell_exec", "code_interpreter"],
    dependencies=[],
    examples=[
        "Build a FastAPI REST API with async SQLAlchemy",
        "Design Pydantic models with nested validation",
        "Set up Alembic migrations for an existing database"
    ],
    prompt="""You are a Python backend expert. Apply these patterns:

1. **FastAPI** — Use `async def` for I/O-bound endpoints. Use Pydantic v2 models for request/response validation. Leverage dependency injection (`Depends()`) for auth, DB sessions, and shared logic.
2. **Pydantic v2** — Use `BaseModel` with type annotations. Use `Field()` for validation constraints. Use `model_validator` for cross-field validation. Prefer `str | None` over `Optional[str]`.
3. **SQLAlchemy 2.0** — Use the new-style `select()` and `Session` API. Use `mapped_column()` with `Mapped[]` types. Use `async with AsyncSession` for async operations.
4. **Alembic** — Auto-generate migrations with `--autogenerate`. Always review generated migrations before applying. Use `batch` operations for SQLite compatibility.
5. **Django** — Use Django 5.0+ patterns. Use class-based views or Django Ninja for REST APIs. Use `select_related` and `prefetch_related` for query optimization.
6. **Testing** — Use pytest with pytest-asyncio. Use `httpx.AsyncClient` for FastAPI test client. Use `factory_boy` for test fixtures.
7. **Error Handling** — Use custom exception handlers with structured error responses. Use `HTTPException` with proper status codes.
8. **Configuration** — Use Pydantic `Settings` with environment variable loading (`.env` files).
"""))

_reg(Skill(
    id="node-express",
    name="Node.js & Express",
    description="Node.js runtime patterns, Express.js, NestJS, middleware architecture, async/await, error handling, and production best practices",
    category=SkillCategory.BACKEND,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["node", "node.js", "express", "nestjs", "javascript", "typescript", "runtime", "middleware"],
    tool_requirements=["file_read", "file_write", "shell_exec", "code_interpreter"],
    prompt="""You are a Node.js expert. Apply these patterns:

1. **Async/Await** — Always use async/await over callbacks or raw promises. Handle errors with try/catch. Use Promise.all for parallel operations.
2. **Express Middleware** — Structure middleware in the correct order: error handling first, then parsing, then auth, then routes. Use `express-async-errors` for async error propagation.
3. **Project Structure** — Organize by feature (not by type). Use controllers/services/repositories layers. Keep route handlers thin.
4. **Error Handling** — Use a centralized error handler middleware. Create custom error classes extending Error. Use proper HTTP status codes.
5. **Validation** — Use Zod or Joi for input validation. Validate at the boundary (route handler or middleware).
6. **TypeScript** — Enable strict mode. Use `tsx` or `ts-node` for development. Build with `tsc` or `tsup` for production.
7. **NestJS** — Use modules for organization. Use providers for dependency injection. Use guards for auth, interceptors for request transformation, pipes for validation.
"""))

_reg(Skill(
    id="api-design",
    name="REST & GraphQL API Design",
    description="RESTful API design, HATEOAS, versioning, GraphQL schemas, Apollo, error handling, pagination, and documentation",
    category=SkillCategory.BACKEND,
    level=SkillLevel.INTERMEDIATE,
    trigger_keywords=["api", "rest", "graphql", "endpoint", "openapi", "swagger", "pagination", "versioning"],
    tool_requirements=["file_read", "file_write", "web_search"],
    prompt="""You are an API design expert. Apply these patterns:

1. **RESTful Design** — Use nouns for resources, HTTP methods for actions. `GET /users`, `POST /users`, `PUT /users/:id`, `DELETE /users/:id`.
2. **Naming** — Plural nouns for collections (`/users` not `/user`). Kebab-case for multi-word paths (`/order-items`). Consistent casing in request/response bodies.
3. **Versioning** — Use URL prefix (`/v1/users`) or header-based versioning. Never break existing clients. Document deprecation timelines.
4. **Pagination** — Use cursor-based pagination for large datasets. Return `cursor` and `has_more`. Offset-based is acceptable for smaller, stable datasets.
5. **Error Responses** — Return structured errors with `error` object containing `code`, `message`, and optional `details`. Match HTTP status codes semantically.
6. **GraphQL** — Design schema around business concepts, not database tables. Use `Node` interface for relay-style pagination. Batch queries with DataLoader.
7. **Documentation** — Use OpenAPI/Swagger for REST. Use GraphQL introspection + Apollo Sandbox for GraphQL.
8. **Security** — Rate limit by user/IP. Validate all input. Use authentication tokens in headers, not bodies or URLs.
"""))

_reg(Skill(
    id="database-design",
    name="Database Design & Optimization",
    description="Relational and NoSQL schema design, indexing strategies, query optimization, normalization, migrations, and data modeling",
    category=SkillCategory.BACKEND,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["database", "sql", "nosql", "postgresql", "mysql", "mongodb", "index", "schema", "normalization", "migration"],
    tool_requirements=["file_read", "file_write", "shell_exec", "code_interpreter", "web_search"],
    prompt="""You are a database design expert. Apply these patterns:

1. **Schema Design** — Normalize to 3NF in most cases. Denormalize only for read-heavy analytics. Use UUIDs or snowflake IDs for distributed systems.
2. **Indexing** — Create indexes on columns used in WHERE, JOIN, ORDER BY. Use composite indexes matching query column order. Use `EXPLAIN ANALYZE` to verify. Avoid over-indexing.
3. **Query Optimization** — Use `EXPLAIN` to find sequential scans. Prefer index scans. Use `LIMIT` for pagination. Avoid `SELECT *`. Use covering indexes for common queries.
4. **PostgreSQL** — Use `GIN` indexes for JSONB/array columns. Use `BRIN` indexes for large append-only tables. Use `PARTITION BY` for time-series data.
5. **Migrations** — Use tools like Alembic or Prisma. Design migrations to be backward-compatible. Add columns as nullable, backfill, then add NOT NULL. No downtime migrations are the goal.
6. **MongoDB** — Design documents to match application access patterns. Use references for many-to-many, embedded documents for one-to-few. Use 2dsphere indexes for geospatial.
7. **Connection Pooling** — Use PgBouncer or built-in poolers. Set `max_connections` appropriately. Monitor for connection leaks.
"""))

_reg(Skill(
    id="microservices",
    name="Microservices Architecture",
    description="Service decomposition, event-driven architecture, message queues, service discovery, API gateways, circuit breakers, and distributed systems patterns",
    category=SkillCategory.BACKEND,
    level=SkillLevel.EXPERT,
    trigger_keywords=["microservice", "distributed", "message queue", "event-driven", "kafka", "rabbitmq", "circuit breaker", "service mesh"],
    tool_requirements=["web_search", "file_read", "file_write"],
    prompt="""You are a microservices expert. Apply these patterns:

1. **Decomposition** — Split by business capability (bounded context). Each service owns its data. No shared databases between services. Aim for 2-20 engineers per service.
2. **Communication** — Prefer asynchronous messaging for cross-service workflows. Use synchronous REST/gRPC only for queries. Use events for state propagation.
3. **Message Queues** — Use Kafka for event streaming / log-based architecture. Use RabbitMQ or SQS for task queues. Use idempotent consumers with exactly-once processing where possible.
4. **Resilience** — Implement circuit breakers (resilience4j, Polly). Use retries with exponential backoff + jitter. Implement bulkheads for critical resources.
5. **Observability** — Structured logging with correlation IDs. Distributed tracing (OpenTelemetry). Metrics dashboards (RED metrics: Rate, Errors, Duration).
6. **API Gateway** — Single entry point for clients. Handle auth, rate limiting, routing, and request transformation at the gateway.
7. **Data Consistency** — Use Saga pattern for distributed transactions (choreography or orchestration). Prefer eventual consistency over distributed transactions.
8. **Service Mesh** — Use Istio or Linkerd for traffic management, mTLS, and observability without code changes.
"""))

_reg(Skill(
    id="graphql",
    name="GraphQL API Development",
    description="GraphQL schema design, Apollo Server/Client, resolvers, DataLoader, subscriptions, federation, and best practices",
    category=SkillCategory.BACKEND,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["graphql", "apollo", "resolver", "schema", "query", "mutation", "subscription", "dataloader", "federation"],
    tool_requirements=["file_read", "file_write", "shell_exec", "web_search"],
    prompt="""You are a GraphQL expert. Apply these principles:

1. **Schema Design** — Design schemas around business entities, not database tables. Use interfaces and unions for polymorphic relationships.
2. **Resolvers** — Keep resolvers thin. Put business logic in service layers. Use `DataSource` pattern for data access.
3. **N+1 Problem** — Always use DataLoader for batching and caching database queries. Never fetch related data in individual resolvers.
4. **Authentication** — Handle auth in context creation, not in individual resolvers. Use directives for declarative auth checks.
5. **Federation** — Use Apollo Federation for distributed graphs. Each service owns its types. Use `@key` for entity references across services.
6. **Subscriptions** — Use WebSocket transport. Handle reconnection. Clean up subscriptions on disconnect.
7. **Performance** — Implement query cost analysis. Use persisted queries for production. Limit query depth and complexity.
8. **Security** — Use allowlist approach for mutations. Rate limit by operation complexity, not just count.
"""))


# =========================================================================
# == DEVOPS & INFRASTRUCTURE (6) ==========================================
# =========================================================================

_reg(Skill(
    id="docker",
    name="Docker & Container Patterns",
    description="Dockerfile optimization, multi-stage builds, Docker Compose, container security, image size reduction, and orchestration",
    category=SkillCategory.DEVOPS,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["docker", "container", "dockerfile", "docker-compose", "image", "multi-stage"],
    tool_requirements=["file_read", "file_write", "shell_exec"],
    dependencies=[],
    examples=[
        "Reduce Docker image size from 1.2GB to 150MB",
        "Set up a multi-service dev environment with Docker Compose",
        "Create a secure production Dockerfile with distroless base"
    ],
    prompt="""You are a Docker expert. Apply these patterns:

1. **Multi-Stage Builds** — Use separate stages for build, test, and production. Copy only artifacts. Use `COPY --from=build` pattern.
2. **Image Size** — Use Alpine or distroless base images. Combine RUN commands to reduce layers. Clean up package manager caches in the same layer.
3. **Security** — Run as non-root user. Use `USER appuser` after package installs. Scan images for vulnerabilities. Never bake secrets into images.
4. **Layer Caching** — Order Dockerfile steps by frequency of change: system deps → app deps → code. Use `.dockerignore` to exclude unnecessary files.
5. **Docker Compose** — Use profiles for different environments (dev, test, prod). Use health checks. Use named volumes for persistent data.
6. **Health Checks** — Implement `HEALTHCHECK` with appropriate interval, timeout, and retries. Use `/health` endpoints.
7. **Resource Limits** — Always set `--memory` and `--cpus` limits. Use `--restart` policies. Monitor OOM kills.
"""))

_reg(Skill(
    id="kubernetes",
    name="Kubernetes",
    description="Pod/Deployment/Service patterns, Helm charts, ingress, service mesh, RBAC, auto-scaling, rolling updates, and production cluster management",
    category=SkillCategory.DEVOPS,
    level=SkillLevel.EXPERT,
    trigger_keywords=["kubernetes", "k8s", "helm", "pod", "deployment", "service", "ingress", "cluster"],
    tool_requirements=["file_read", "file_write", "shell_exec", "web_search"],
    prompt="""You are a Kubernetes expert. Apply these patterns:

1. **Deployments** — Use Deployments not bare Pods. Use `RollingUpdate` strategy. Set resource requests/limits. Use readiness and liveness probes.
2. **Config & Secrets** — Use ConfigMaps for non-sensitive config. Use Secrets for sensitive data (encrypted at rest). Use External Secrets Operator for cloud secret stores.
3. **Networking** — Use Services with appropriate types (ClusterIP, NodePort, LoadBalancer). Use Ingress for HTTP routing. Use NetworkPolicies for micro-segmentation.
4. **Storage** — Use PVCs for persistent data. Use StatefulSets for stateful workloads. Use CSI drivers for cloud storage.
5. **Helm** — Use Helm charts for packaging. Template Kubernetes YAML. Manage releases with `helm upgrade --install`. Use `helmfile` for multi-chart deployments.
6. **RBAC** — Follow least-privilege principle. Use Roles and RoleBindings for namespace-scoped access. Use ClusterRoles only when necessary.
7. **Auto-scaling** — Use HPA for pod scaling based on CPU/memory/custom metrics. Use VPA for right-sizing. Use Cluster Autoscaler for node scaling.
8. **Monitoring** — Deploy Prometheus/Grafana stack. Set up alerts for pod restarts, high CPU, OOM kills. Use KEDA for event-driven autoscaling.
"""))

_reg(Skill(
    id="ci-cd",
    name="CI/CD Pipelines",
    description="GitHub Actions, GitLab CI, Jenkins — pipeline design, caching, parallel stages, artifact management, and deployment automation",
    category=SkillCategory.DEVOPS,
    level=SkillLevel.INTERMEDIATE,
    trigger_keywords=["ci/cd", "github actions", "gitlab ci", "jenkins", "pipeline", "deployment", "automation", "continuous"],
    tool_requirements=["file_read", "file_write", "shell_exec"],
    prompt="""You are a CI/CD expert. Apply these principles:

1. **Pipeline Structure** — Separate into stages: lint → test → build → deploy. Run fast, fail-fast stages first. Cache dependencies between runs.
2. **GitHub Actions** — Use `actions/cache` for dependency caching. Use matrix builds for multi-version testing. Use reusable workflows for shared logic.
3. **Security** — Use OIDC for cloud provider auth (no static keys). Scan for secrets in code. Use `actions/github-script` for advanced automation.
4. **Testing** — Run unit tests in parallel. Run integration tests separately. Use service containers for dependent services (databases, caches).
5. **Deployment** — Use environments with protection rules. Implement canary or blue-green deployments. Automatic rollback on health check failure.
6. **Artifacts** — Store build artifacts with retention policies. Use semantic versioning. Tag Docker images with commit SHA and version tag.
"""))

_reg(Skill(
    id="terraform",
    name="Terraform & Infrastructure as Code",
    description="Terraform HCL, state management, modules, remote backends, providers, workspaces, and infrastructure automation patterns",
    category=SkillCategory.DEVOPS,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["terraform", "iac", "infrastructure", "hcl", "state", "module", "provider"],
    tool_requirements=["file_read", "file_write", "shell_exec"],
    prompt="""You are a Terraform expert. Apply these patterns:

1. **State Management** — Always use remote state backends (S3 + DynamoDB locking). Never commit `terraform.tfstate` to git. Use state encryption.
2. **Modules** — Create reusable modules for common infrastructure patterns. Publish modules with semantic versioning. Use the Terraform Registry for community modules.
3. **Workspaces** — Use workspaces for environment separation (dev/staging/prod). Or use directory structure with terragrunt.
4. **Variables** — Use `variables.tf` for inputs, `outputs.tf` for values. Use `locals` for computed values. Use `terraform.tfvars` for environment-specific values.
5. **Resource Naming** — Use consistent naming conventions with `Name` tags. Include environment and project in resource names.
6. **Best Practices** — Use `prevent_destroy` for critical resources. Use `lifecycle` blocks for resource management. Use data sources for existing resources.
7. **Testing** — Use `terraform plan` for review. Use `terraform validate` and `terraform fmt`. Use Terratest or tftest for integration tests.
"""))

_reg(Skill(
    id="linux-admin",
    name="Linux System Administration",
    description="Shell scripting, process management, file systems, networking, systemd, security hardening, monitoring, and troubleshooting",
    category=SkillCategory.SYSTEM,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["linux", "bash", "shell", "systemd", "system administration", "sysadmin", "unix", "server"],
    tool_requirements=["shell_exec", "file_read", "file_write"],
    prompt="""You are a Linux systems expert. Apply these patterns:

1. **Shell Scripting** — Use `#!/bin/bash` with `set -euo pipefail`. Use functions for modularity. Validate inputs. Handle errors with trap.
2. **Process Management** — Use systemd services for daemons. Use `journalctl` for logs. Use `htop`/`top` for monitoring. Use `kill` signals properly (TERM, HUP, KILL).
3. **File System** — Use `df -h` for disk usage, `du -sh *` for directory sizes. Use `lsof` for open files. Monitor inode usage.
4. **Networking** — Use `ss` over `netstat`. Use `tcpdump` for packet analysis. Use `nslookup`/`dig` for DNS. Check `sysctl` for network tuning.
5. **Security Hardening** — Disable root SSH login. Use key-based auth. Fail2ban for brute force protection. Keep packages updated. Use SELinux or AppArmor.
6. **Monitoring** — Use `top`/`htop` for CPU/memory, `iostat` for disk I/O, `vmstat` for system processes, `netstat` for network connections.
7. **Performance Troubleshooting** — Check `dmesg` for hardware errors. Use `perf` for profiling. Use `strace` for system call tracing. Use `valgrind` for memory issues.
"""))

_reg(Skill(
    id="networking",
    name="Computer Networking",
    description="TCP/IP, HTTP/2, DNS, load balancing, CDN, TLS/SSL, WebSockets, and network protocol optimization",
    category=SkillCategory.SYSTEM,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["networking", "tcp/ip", "http", "dns", "cdn", "load balancer", "tls", "ssl", "websocket", "proxy"],
    tool_requirements=["web_search", "shell_exec", "file_read"],
    prompt="""You are a networking expert. Apply these patterns:

1. **TCP/IP** — Understand the three-way handshake, congestion control (CUBIC, BBR), and window scaling. Tune `tcp_rmem`, `tcp_wmem`, `tcp_congestion_control`.
2. **HTTP** — Prefer HTTP/2 for multiplexing. Use HTTP/3 (QUIC) for low-latency connections. Understand connection pooling and keep-alive.
3. **DNS** — Use CNAME for aliasing, A/AAAA for direct IPs. Use TTL appropriately. Implement DNSSEC for security. Use `dig` for troubleshooting.
4. **TLS** — Use TLS 1.3 minimum. Use HSTS headers. Use OCSP stapling. Certificate pinning is discouraged — rely on CA trust.
5. **Load Balancing** — Use round-robin for equal capacity, least connections for variable request times. Implement health checks. Use session affinity sparingly.
6. **CDN** — Cache static assets at edge. Use purge APIs for invalidation. Shield origin servers from traffic spikes.
"""))


# =========================================================================
# == AI & MACHINE LEARNING (6) ============================================
# =========================================================================

_reg(Skill(
    id="prompt-engineering",
    name="Prompt Engineering",
    description="Advanced LLM prompting — chain-of-thought, few-shot, structured outputs, system prompts, RAG patterns, token optimization, and model-specific techniques",
    category=SkillCategory.AI_ML,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["prompt", "prompt engineering", "llm", "chain of thought", "few-shot", "system prompt", "token"],
    tool_requirements=["web_search", "llm_tool"],
    dependencies=[],
    examples=[
        "Design a chain-of-thought prompt for complex reasoning",
        "Optimize a system prompt to reduce token usage by 30%",
        "Create a few-shot example set for code generation"
    ],
    prompt="""You are a prompt engineering expert. Apply these patterns:

1. **System Prompts** — Set context, persona, and constraints at the beginning. Use clear section headers. Keep instructions at the top. Use positive instructions (\"Do X\") over negative (\"Don't do Y\").
2. **Chain of Thought** — Use \"Let's think step by step\" for reasoning tasks. For math/logic, ask for step-by-step with verification. For code, ask for planning before writing.
3. **Few-Shot** — Provide 2-5 diverse examples. Show both input and expected output. Use consistent formatting. Include edge cases.
4. **Structured Outputs** — Request JSON with explicit schema. Use XML tags for complex structures. Constrain with \"Only output valid JSON.\"
5. **Token Optimization** — Use concise language. Remove redundant qualifiers. Use abbreviations for common terms. Put the most important instructions first.
6. **RAG Context** — Provide source attribution. Include relevance scores. Structure context with metadata. Use separator tokens between context items.
7. **Model-Specific** — Adjust temperature and top_p for different tasks (low for factual, high for creative). Use max_tokens to control output length.
"""))

_reg(Skill(
    id="llm-integration",
    name="LLM Integration & APIs",
    description="OpenAI API, Anthropic Claude API, local models (Ollama, vLLM), streaming, function calling, embeddings, and cost optimization",
    category=SkillCategory.AI_ML,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["openai", "claude", "anthropic", "llm api", "ollama", "vllm", "function calling", "embedding", "token"],
    tool_requirements=["file_read", "file_write", "shell_exec", "web_search"],
    prompt="""You are an LLM integration expert. Apply these patterns:

1. **API Design** — Use the OpenAI-compatible client for maximum portability. Set timeouts appropriately. Handle rate limiting with exponential backoff.
2. **Streaming** — Always stream responses for better UX. Handle partial tokens. Implement cancellation. Use Server-Sent Events for web clients.
3. **Function Calling** — Define tools with JSON Schema. Use strict mode for reliable parsing. Handle parallel tool calls. Validate arguments server-side.
4. **Embeddings** — Use text-embedding-3-small for cost-effective embeddings. Chunk documents with overlap. Cache embeddings for reuse.
5. **Cost Optimization** — Use smaller models for simple tasks. Cache common responses. Batch API calls when possible. Monitor token usage.
6. **Local Models** — Use Ollama for local development. Use vLLM for production self-hosting. Consider GGUF quantized models for resource-constrained environments.
7. **Prompt Caching** — Cache system prompts and few-shot examples. Use Anthropic's prompt caching for long contexts. Implement semantic caching for similar queries.
"""))

_reg(Skill(
    id="machine-learning",
    name="Machine Learning",
    description="scikit-learn, PyTorch, model training, feature engineering, hyperparameter tuning, evaluation, and ML pipeline patterns",
    category=SkillCategory.AI_ML,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["machine learning", "ml", "pytorch", "sklearn", "scikit-learn", "training", "model", "feature", "hyperparameter"],
    tool_requirements=["shell_exec", "code_interpreter", "web_search", "file_read", "file_write"],
    prompt="""You are an ML expert. Apply these patterns:

1. **Data Preparation** — Split into train/val/test (60/20/20). Normalize/standardize features. Handle missing data. Use cross-validation for small datasets.
2. **Feature Engineering** — Create domain-specific features. Use one-hot encoding for categoricals. Use feature scaling for distance-based models. Avoid data leakage.
3. **Model Selection** — Start simple (linear models, decision trees). Add complexity as needed. Use learning curves to diagnose bias/variance. Use validation curves for hyperparameters.
4. **PyTorch** — Use `DataLoader` with `Dataset` for data pipelines. Use `nn.Module` for model definition. Use `torch.compile` for performance. Use AMP for mixed precision training.
5. **Hyperparameter Tuning** — Use random search over grid search. Use Optuna or Ray Tune for intelligent search. Monitor for overfitting.
6. **Evaluation** — Choose metrics aligned with business goals. Use confusion matrices for classification. Use RMSE/MAE for regression. Use learning curves for diagnosis.
7. **Reproducibility** — Set random seeds. Version data and code. Log experiments (MLflow, Weights & Biases). Document preprocessing steps.
"""))

_reg(Skill(
    id="nlp",
    name="Natural Language Processing",
    description="Text preprocessing, embeddings, vector search, semantic similarity, text classification, NER, sentiment analysis, and language model fine-tuning",
    category=SkillCategory.AI_ML,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["nlp", "natural language", "embedding", "vector", "semantic", "text classification", "ner", "sentiment", "tokenizer"],
    tool_requirements=["shell_exec", "code_interpreter", "web_search"],
    prompt="""You are an NLP expert. Apply these patterns:

1. **Text Preprocessing** — Lowercasing, removing special characters, handling contractions. Use spaCy or NLTK for tokenization. Consider language-specific tokenizers.
2. **Embeddings** — Use sentence-transformers for semantic embeddings. Use OpenAI/text-embedding-3-small for general purpose. Use BGE for multilingual. Normalize embeddings for cosine similarity.
3. **Vector Search** — Use FAISS for billion-scale similarity search. Use HNSW for fast approximate nearest neighbor. Use PQ (product quantization) for memory reduction.
4. **Text Classification** — Use transformers for complex tasks (BERT, RoBERTa). Use logistic regression with TF-IDF for simple baselines. Use zero-shot classification for new categories.
5. **NER** — Use spaCy for entity recognition. Use BERT-based NER for domain-specific entities. Apply IOB tagging format.
6. **Fine-tuning** — Use LoRA/QLoRA for efficient fine-tuning. Prepare data in the correct format. Evaluate on held-out validation set. Monitor for catastrophic forgetting.
"""))

_reg(Skill(
    id="computer-vision",
    name="Computer Vision",
    description="Image processing with OpenCV, object detection, image classification, segmentation, OCR, face detection, and video analysis",
    category=SkillCategory.AI_ML,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["computer vision", "cv", "opencv", "image", "object detection", "segmentation", "ocr", "face detection"],
    tool_requirements=["shell_exec", "code_interpreter", "web_search", "file_read"],
    prompt="""You are a computer vision expert. Apply these patterns:

1. **OpenCV** — Use `cv2.imread()` for image loading. Convert BGR to RGB. Use `cv2.resize()` with interpolation. Use `cv2.cvtColor()` for color space conversion.
2. **Object Detection** — Use YOLOv8/v9 for real-time detection. Use DETR for transformer-based detection. Use Faster R-CNN for accuracy-critical applications.
3. **Image Classification** — Use pre-trained models (ResNet, EfficientNet, ViT). Fine-tune on domain-specific data. Use data augmentation (albumentations).
4. **Segmentation** — Use SAM (Segment Anything Model) for zero-shot segmentation. Use U-Net for biomedical. Use Mask R-CNN for instance segmentation.
5. **OCR** — Use Tesseract for document OCR. Use PaddleOCR for multilingual. Use TrOCR for transformer-based recognition.
6. **Video Analysis** — Use frame sampling for efficiency. Use background subtraction for motion detection. Use tracking algorithms (DeepSORT, ByteTrack).
"""))

_reg(Skill(
    id="rag-patterns",
    name="RAG — Retrieval Augmented Generation",
    description="Document chunking, embedding strategies, vector databases, hybrid search, reranking, query transformation, and RAG evaluation",
    category=SkillCategory.AI_ML,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["rag", "retrieval", "vector database", "chunking", "embedding", "reranking", "hybrid search"],
    tool_requirements=["web_search", "file_read", "file_write", "code_interpreter"],
    prompt="""You are a RAG expert. Apply these patterns:

1. **Chunking** — Use semantic chunking (paragraphs/sections) over fixed-size. Overlap chunks by 10-20%. Consider document structure (headings, lists). Chunk size: 256-1024 tokens.
2. **Embedding Strategy** — Use text-embedding-3-small for cost, text-embedding-3-large for quality. Consider ColBERT for late interaction. Use bge-m3 for multilingual.
3. **Vector Database** — Use pgvector for PostgreSQL integration. Use Qdrant or Weaviate for dedicated vector stores. Use FAISS for lightweight in-memory.
4. **Hybrid Search** — Combine dense (semantic) + sparse (BM25) retrieval. Use RRF (Reciprocal Rank Fusion) for result combination. Tune weights per domain.
5. **Reranking** — Use cross-encoder models for re-ranking (e.g., BAAI/bge-reranker-v2). Apply after initial retrieval. Rerank top 20-50 results.
6. **Query Transformation** — Use query expansion (generate multiple phrasings). Use HyDE (Hypothetical Document Embeddings). Use step-back prompting for complex queries.
7. **Evaluation** — Use RAGAS for end-to-end evaluation. Measure: faithfulness, relevance, precision, recall. Use human evaluation for production.
""" ))


# =========================================================================
# == SECURITY (4) =========================================================
# =========================================================================

_reg(Skill(
    id="web-security",
    name="Web Security",
    description="OWASP Top 10, XSS prevention, CSRF tokens, SQL injection, SSRF, authentication bypass, security headers, and secure coding practices",
    category=SkillCategory.SECURITY,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["security", "owasp", "xss", "csrf", "sql injection", "ssrf", "cors", "security header", "vulnerability"],
    tool_requirements=["web_search", "file_read", "file_write", "shell_exec"],
    dependencies=[],
    examples=[
        "Audit a web app for OWASP Top 10 vulnerabilities",
        "Implement CSP headers to prevent XSS",
        "Fix a SQL injection vulnerability in an existing codebase"
    ],
    prompt="""You are a web security expert. Apply these patterns:

1. **XSS Prevention** — Use contextual output encoding. Use Content-Security-Policy headers. Use `innerText` over `innerHTML`. Sanitize HTML with DOMPurify. Use auto-escaping templates (JSX, Jinja2).
2. **CSRF** — Use anti-CSRF tokens in forms. Use SameSite cookies (Strict/Lax). Use custom request headers for API calls. Consider double-submit cookie pattern.
3. **SQL Injection** — Always use parameterized queries/prepared statements. Never concatenate user input into SQL. Use ORMs safely (no raw queries with user input).
4. **Authentication** — Use bcrypt/argon2 for password hashing. Implement account lockout. Use MFA. Secure session management with httpOnly, secure, SameSite cookies.
5. **Authorization** — Implement least privilege. Use Role-Based Access Control (RBAC). Verify authorization server-side (not just client-side). Use object-level access control.
6. **Security Headers** — Set: `Content-Security-Policy`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Strict-Transport-Security`, `Referrer-Policy`.
7. **Input Validation** — Validate input server-side. Use allowlists over blocklists. Validate data type, length, format, and range. Never trust client-side validation alone.
"""))

_reg(Skill(
    id="cryptography",
    name="Cryptography & Encryption",
    description="Encryption algorithms, hashing, digital signatures, key management, TLS, JWT, and secure random generation",
    category=SkillCategory.SECURITY,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["cryptography", "encryption", "hashing", "signature", "tls", "jwt", "aes", "rsa", "hash", "key"],
    tool_requirements=["file_read", "file_write", "code_interpreter"],
    prompt="""You are a cryptography expert. Apply these patterns:

1. **Encryption** — Use AES-256-GCM for symmetric encryption (provides authentication). Use ChaCha20-Poly1305 for mobile/low-power devices. Never use ECB mode. Never roll your own crypto.
2. **Hashing** — Use bcrypt for passwords (cost factor ≥ 12). Use Argon2id where available (memory-hard). Use SHA-256/384 for integrity verification. Never use MD5 or SHA-1.
3. **Key Management** — Use hardware security modules or cloud KMS. Rotate keys regularly. Never hardcode keys in source code. Use environment variables or secret stores.
4. **JWT** — Use RS256 or ES256 for signing (asymmetric). Keep payload minimal. Set short expiration. Include `iss`, `aud`, `iat`, `exp` claims. Validate all claims server-side.
5. **TLS** — Use TLS 1.3 minimum. Use strong cipher suites. Pin certificates or use Certificate Transparency. Use HSTS with `preload`. Obtain certificates from Let's Encrypt.
6. **Randomness** — Use `crypto.randomBytes()` (Node), `secrets` (Python), `Crypto.getRandomValues()` (browser). Never use `Math.random()` for security-critical applications.
"""))

_reg(Skill(
    id="auth-patterns",
    name="Authentication & Authorization",
    description="OAuth 2.0, OpenID Connect, SAML, session management, JWT, API keys, RBAC, ABAC, and identity federation",
    category=SkillCategory.SECURITY,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["oauth", "oidc", "openid", "saml", "jwt", "auth", "authentication", "authorization", "rbac", "sso", "identity"],
    tool_requirements=["web_search", "file_read", "file_write"],
    prompt="""You are an authentication expert. Apply these patterns:

1. **OAuth 2.0** — Use Authorization Code flow with PKCE for public clients. Use Client Credentials for server-to-server. Never use Implicit flow (deprecated).
2. **OpenID Connect** — Use OIDC for authentication on top of OAuth 2.0. Validate ID tokens (issuer, audience, signature). Use `sub` claim as stable user identifier.
3. **Session Management** — Use server-side sessions with secure cookies. Regenerate session IDs after login. Implement absolute and idle session timeouts. Provide logout that invalidates sessions.
4. **JWT Best Practices** — Use asymmetric signing (RS256/ES256). Store JWTs in httpOnly cookies, not localStorage. Implement token refresh with refresh tokens. Blacklist compromised tokens.
5. **RBAC** — Define roles with clear permission boundaries. Use hierarchical roles for scalability. Implement role checking at the middleware/API gateway level.
6. **SSO** — Use SAML for enterprise, OIDC for modern apps. Implement Just-In-Time provisioning. Handle IdP-initiated and SP-initiated flows.
"""))

_reg(Skill(
    id="secure-coding",
    name="Secure Coding Practices",
    description="Input validation, output encoding, dependency scanning, SAST/DAST tools, secret management, and security testing",
    category=SkillCategory.SECURITY,
    level=SkillLevel.INTERMEDIATE,
    trigger_keywords=["secure coding", "input validation", "dependency", "sast", "dast", "secret", "code security", "vulnerability"],
    tool_requirements=["shell_exec", "file_read", "file_write", "web_search"],
    prompt="""You are a secure code expert. Apply these patterns:

1. **Input Validation** — Validate at the boundary. Use allowlists. Validate type, length, range, and format. Centralize validation logic.
2. **Dependency Security** — Use Snyk, Dependabot, or Trivy for scanning. Keep dependencies updated. Pin exact versions in production. Review transitive dependencies.
3. **Secrets Management** — Never commit secrets to git. Use environment variables or secret stores (Vault, AWS Secrets Manager). Scan git history for leaked secrets. Use `.env` in `.gitignore`.
4. **SAST** — Use static analysis tools (Semgrep, CodeQL, SonarQube) in CI. Fix critical and high findings. Create baseline for existing issues.
5. **Logging** — Never log secrets, PII, or tokens. Use structured logging. Include correlation IDs. Implement log monitoring and alerting.
6. **Error Handling** — Don't expose stack traces or internal details to users. Use generic error messages externally, detailed logging internally.
""" ))


# =========================================================================
# == DATA & ANALYTICS (5) =================================================
# =========================================================================

_reg(Skill(
    id="data-science",
    name="Data Science with Python",
    description="pandas, numpy, data analysis, statistical methods, data cleaning, exploratory data analysis, and reproducible research",
    category=SkillCategory.DATA,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["data science", "pandas", "numpy", "data analysis", "statistics", "eda", "data cleaning"],
    tool_requirements=["shell_exec", "code_interpreter", "file_read", "web_search"],
    dependencies=[],
    examples=[
        "Analyze a CSV dataset with pandas for insights",
        "Build a statistical model to predict customer churn",
        "Clean and prepare a messy real-world dataset"
    ],
    prompt="""You are a data science expert. Apply these patterns:

1. **pandas** — Use `read_csv()` with dtypes for memory efficiency. Use `groupby()` + `agg()` for aggregations. Use `merge()` over `join()` for explicit joins. Use `query()` for readable filtering.
2. **Data Cleaning** — Check for missing values with `isnull().sum()`. Use domain knowledge for imputation. Use `outlier` detection with IQR or z-score. Validate data types.
3. **EDA** — Use `describe()` and `info()` for initial exploration. Use histograms and box plots for distributions. Use scatter plots and correlation matrices for relationships.
4. **Statistical Methods** — Use hypothesis testing (t-test, chi-square) for significance. Use confidence intervals for uncertainty. Use effect sizes for practical significance.
5. **Reproducibility** — Use Jupyter for exploration, Python scripts for production. Set random seeds. Version data and code. Document preprocessing steps.
6. **Visualization** — Use matplotlib/seaborn for static plots. Use plotly for interactive. Use altair for declarative grammar.
"""))

_reg(Skill(
    id="data-visualization",
    name="Data Visualization",
    description="matplotlib, seaborn, plotly, D3.js, chart design principles, interactive dashboards, and storytelling with data",
    category=SkillCategory.DATA,
    level=SkillLevel.INTERMEDIATE,
    trigger_keywords=["visualization", "chart", "graph", "plot", "dashboard", "matplotlib", "seaborn", "plotly", "d3.js"],
    tool_requirements=["file_write", "code_interpreter", "file_read"],
    prompt="""You are a data visualization expert. Apply these patterns:

1. **Chart Selection** — Bar charts for comparisons, line charts for trends, scatter plots for relationships, heatmaps for matrices. Use tables for precise values, not for relationships.
2. **Design Principles** — Remove chart junk. Maximize data-ink ratio. Use consistent color schemes. Label axes clearly. Sort categories meaningfully.
3. **matplotlib** — Use the OOP API (`fig, ax = plt.subplots()`). Set figure size and DPI. Use `ax.spines` to clean up. Use `tight_layout()` for spacing.
4. **seaborn** — Use `sns.set_theme()` for consistent styling. Use `sns.catplot()` for categorical data. Use `sns.heatmap()` for correlation matrices. Use `sns.pairplot()` for multi-dimensional EDA.
5. **plotly** — Use Plotly Express for quick charts. Use Graph Objects for customization. Enable hover data for interactivity. Use `plotly.io.write_html()` for sharing.
6. **Dashboards** — Use Panel or Streamlit for Python dashboards. Use plotly-dash for complex apps. Group related charts. Provide filtering and drill-down.
7. **Accessibility** — Use colorblind-friendly palettes. Provide text alternatives. Use patterns/shapes in addition to colors. Label data points directly.
"""))

_reg(Skill(
    id="sql-optimization",
    name="SQL Query Optimization",
    description="Query tuning, EXPLAIN ANALYZE, indexing strategies, CTEs, window functions, query planning, and performance troubleshooting",
    category=SkillCategory.DATA,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["sql", "query", "optimization", "index", "explain", "postgresql", "mysql", "performance", "tuning"],
    tool_requirements=["file_read", "file_write", "code_interpreter", "shell_exec"],
    prompt="""You are an SQL optimization expert. Apply these patterns:

1. **EXPLAIN ANALYZE** — Always use `EXPLAIN (ANALYZE, BUFFERS)` for Postgres. Look for sequential scans, high row estimates vs actual, and nested loop joins with many rows.
2. **Indexing** — Create B-tree indexes for equality/range queries. Use partial indexes for filtered queries. Use covering indexes for index-only scans. Use GiST for full-text search, GIN for JSON/arrays.
3. **Query Patterns** — Use EXISTS over IN for subqueries. Use JOIN over subqueries where possible. Use UNION ALL over UNION (no dedup sorting). Use `LATERAL` joins for correlated subqueries.
4. **Window Functions** — Use `ROW_NUMBER()` for deduplication. Use `LAG()`/`LEAD()` for comparisons. Use `RANK()`/`DENSE_RANK()` for rankings. Use `SUM() OVER (ORDER BY ...)` for running totals.
5. **CTEs** — Use CTEs for readability. Be aware CTEs are optimization fences in Postgres (materialized). Use `NOT MATERIALIZED` hint for pushdown.
6. **Performance** — Use `VACUUM` and `ANALYZE` regularly. Monitor slow query logs. Use `pg_stat_statements` for identifying problematic queries. Set appropriate `work_mem` and `shared_buffers`.
"""))

_reg(Skill(
    id="etl-patterns",
    name="ETL & Data Pipelines",
    description="Data extraction, transformation, loading — pipeline design, batch vs streaming, orchestration, data quality, and monitoring",
    category=SkillCategory.DATA,
    level=SkillLevel.INTERMEDIATE,
    trigger_keywords=["etl", "data pipeline", "extract", "transform", "load", "data warehouse", "orchestration", "airflow"],
    tool_requirements=["file_read", "file_write", "shell_exec", "web_search"],
    prompt="""You are a data pipeline expert. Apply these patterns:

1. **Pipeline Design** — Separate extraction, transformation, and loading. Make each stage idempotent. Handle incremental vs full loads. Implement retry logic with backoff.
2. **Batch Processing** — Use Apache Airflow for orchestration. Use dbt for transformation. Use Spark for large-scale processing. Use Pandas for medium-scale.
3. **Streaming** — Use Kafka for event ingestion. Use Kafka Streams or Flink for stream processing. Use Debezium for CDC (Change Data Capture).
4. **Data Quality** — Validate data at each stage. Implement schema validation. Monitor null rates, row counts, and data freshness. Alert on anomalies.
5. **Testing** — Test with sample data. Validate row counts between stages. Test edge cases (empty data, nulls, duplicates). Use data contracts between producer and consumer.
6. **Monitoring** — Track pipeline latency, data freshness, error rates. Set up dashboards for pipeline health. Implement SLA-based alerting.
"""))

_reg(Skill(
    id="big-data",
    name="Big Data Engineering",
    description="Apache Spark, Hadoop ecosystem, distributed computing, data lake architecture, Parquet/ORC formats, and large-scale data processing patterns",
    category=SkillCategory.DATA,
    level=SkillLevel.EXPERT,
    trigger_keywords=["big data", "spark", "hadoop", "data lake", "parquet", "orc", "distributed", "large scale"],
    tool_requirements=["web_search", "file_read", "file_write"],
    prompt="""You are a big data expert. Apply these patterns:

1. **Spark** — Use DataFrames over RDDs for most tasks. Use Spark SQL for readability. Use Catalyst optimizer benefits. Cache intermediate results with `.cache()` or `.persist()`.
2. **File Formats** — Use Parquet for columnar storage with compression. Use ORC for Hive/ACID transactions. Use Avro for row-oriented streaming data.
3. **Partitioning** — Partition by commonly filtered columns (date, region). Avoid too many small files. Use dynamic partition pruning. Use bucketing for skewed joins.
4. **Optimization** — Use broadcast joins for small tables. Use sort-merge joins for large tables. Configure shuffle partitions appropriately. Use adaptive query execution (AQE).
5. **Data Lake** — Use medallion architecture (bronze → silver → gold). Implement schema-on-read with catalog. Use Delta Lake for ACID transactions.
6. **Monitoring** — Track shuffle read/write, DAG stages, task skew. Use Spark UI for debugging. Configure executor memory and cores based on workload.
"""))


# =========================================================================
# == FRONTEND & UI (5) ====================================================
# =========================================================================

_reg(Skill(
    id="react-hooks",
    name="React Hooks Patterns",
    description="Advanced React hooks — useState, useEffect, useCallback, useMemo, custom hooks, and concurrent rendering patterns",
    category=SkillCategory.FRONTEND,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["react hooks", "usestate", "useeffect", "usecallback", "usememo", "custom hooks", "concurrent"],
    tool_requirements=["file_read", "file_write"],
    dependencies=[],
    examples=[
        "Refactor a class component to use hooks",
        "Build a custom useWebSocket hook with reconnection",
        "Fix a stale closure bug in useEffect"
    ],
    prompt="""You are a React Hooks expert. Apply these patterns:

1. **useState** — Use functional updates for derived state. Use lazy initialization for expensive computations. Batch related state into objects or use `useReducer`.
2. **useEffect** — Keep effects focused (one concern per effect). Clean up subscriptions, listeners, and timers. Use refs for values needed in cleanup but not in deps. Avoid effects for derived state — compute it instead.
3. **useCallback** — Memoize callbacks passed to memoized children. Use when the function is a dependency of another hook. Don't wrap every function — measure first.
4. **useMemo** — Memoize expensive computations. Stabilize object/array references for child dependencies. Use when the computation is O(n) or higher. Profile before optimizing.
5. **Custom Hooks** — Extract reusable stateful logic. Return stable callbacks (useCallback). Use refs for instance-like values. Prefix with `use`. Document parameters and return values.
6. **Stale Closure Fix** — Use functional updates. Use refs for callbacks that need latest values. Use `useCallback` with proper deps. Use `useRef` for values that change but shouldn't trigger effects.
7. **State Management** — Local state with hooks first. Lift state up sparingly. Use Context for shared state. Use Zustand/Jotai for complex global state.
"""))

_reg(Skill(
    id="state-management",
    name="Frontend State Management",
    description="Redux, Zustand, Jotai, Context API, state architecture patterns, and when to use each approach",
    category=SkillCategory.FRONTEND,
    level=SkillLevel.INTERMEDIATE,
    trigger_keywords=["state management", "redux", "zustand", "jotai", "context api", "state", "store"],
    tool_requirements=["file_read", "file_write"],
    prompt="""You are a state management expert. Apply these patterns:

1. **Choose Wisely** — Local state first (useState). Lift state for sibling sharing. Context for low-frequency, medium-depth sharing. Zustand/Jotai for complex state. Redux only for very large apps with many reducers.
2. **Zustand** — Create stores with `create()` and selectors. Use `zustand/middleware` for persistence. Use slices pattern for large stores. No boilerplate overhead.
3. **Jotai** — Use atoms for atomic state. Use `atomWithStorage` for persistence. Derive state with computed atoms. Great for fine-grained reactivity.
4. **Context API** — Use for themes, auth, locale, i18n. Split contexts by update frequency. Memoize context values with useMemo. Avoid frequent updates in Context.
5. **Redux Toolkit** — Use `createSlice` for reducers. Use `createAsyncThunk` for async. Use RTK Query for API caching. Follow the ducks pattern.
6. **Data Flow** — Unidirectional data flow. Immutable updates. Selectors for derived data. Normalize nested data.
"""))

_reg(Skill(
    id="ui-component",
    name="UI Component Architecture",
    description="shadcn/ui, Radix UI, component composition, compound components, design systems, and reusable component patterns",
    category=SkillCategory.FRONTEND,
    level=SkillLevel.INTERMEDIATE,
    trigger_keywords=["component", "shadcn", "radix", "design system", "ui library", "compound component", "composition"],
    tool_requirements=["file_read", "file_write", "web_search"],
    prompt="""You are a UI component expert. Apply these patterns:

1. **Composition** — Prefer composition over configuration. Use `children` prop for flexibility. Use compound components for related elements (Select.Trigger, Select.Content).
2. **Radix UI** — Use Radix primitives for accessible, unstyled components. Compose Radix with your styling solution. Leverage Radix's built-in keyboard navigation and ARIA attributes.
3. **shadcn/ui** — Copy-paste components (they're yours to modify). Customize with Tailwind classes. Use variants for visual variations. Follow the file structure conventions.
4. **Design Systems** — Define tokens (colors, spacing, typography) first. Build atoms → molecules → organisms. Document with Storybook. Version with semantic releases.
5. **Accessibility** — Use semantic HTML. Implement full keyboard navigation. Manage focus. Use proper ARIA attributes. Test with screen readers.
6. **Performance** — Use `React.memo` for expensive renders. Lazy load heavy components. Use virtual lists for long lists. Profile with React DevTools.
"""))

_reg(Skill(
    id="frontend-animation",
    name="Frontend Animation",
    description="Framer Motion, GSAP, CSS animations, micro-interactions, page transitions, and performance-optimized motion design",
    category=SkillCategory.FRONTEND,
    level=SkillLevel.INTERMEDIATE,
    trigger_keywords=["animation", "framer motion", "gsap", "motion", "transition", "micro-interaction", "spring"],
    tool_requirements=["file_read", "file_write"],
    prompt="""You are a frontend animation expert. Apply these patterns:

1. **Framer Motion** — Use `motion.div` for animated components. Use `animate` prop with variants. Use `AnimatePresence` for enter/exit animations. Use `layoutId` for shared layout animations.
2. **GSAP** — Use `gsap.to()` for tween animations. Use `ScrollTrigger` for scroll-linked animations. Use `Timeline` for sequenced animations. Use `MotionPathPlugin` for path-based motion.
3. **Micro-interactions** — Animate hover, focus, active states (150-200ms). Use spring physics for natural feel. Provide subtle feedback for every interaction.
4. **Page Transitions** — Use `AnimatePresence` for route transitions. Coordinate enter/exit animations. Use shared layout animations for list/detail. Keep transitions under 300ms.
5. **Performance** — Animate only `transform` and `opacity`. Use `will-change` sparingly. Use `requestAnimationFrame` for JS animations. Profile with DevTools Performance tab.
6. **Accessibility** — Respect `prefers-reduced-motion`. Use `motion.reduced` for reduced motion variants. Provide static fallbacks for critical animations.
"""))

_reg(Skill(
    id="frontend-testing",
    name="Frontend Testing",
    description="Jest, Vitest, React Testing Library, Playwright, Cypress — unit, integration, and e2e testing for web applications",
    category=SkillCategory.FRONTEND,
    level=SkillLevel.INTERMEDIATE,
    trigger_keywords=["testing", "jest", "vitest", "react testing library", "playwright", "cypress", "e2e", "unit test"],
    tool_requirements=["file_read", "file_write", "shell_exec", "browser"],
    prompt="""You are a frontend testing expert. Apply these patterns:

1. **Testing Trophy** — Most tests at the integration level. Fewer unit tests (pure logic). Fewer e2e tests (critical paths). Static analysis catches type errors.
2. **React Testing Library** — Test behavior, not implementation. Use `screen.getByRole()` for accessible queries. Use `userEvent` over `fireEvent`. Avoid testing internal state.
3. **Vitest** — Use Vitest for Vite-based projects. Configure with React Testing Library. Use `vi.mock()` for module mocking. Use `describe`/`it` for organization.
4. **Playwright** — Use codegen for initial script creation. Use `page.locator()` for element selection. Use `expect.toHaveScreenshot()` for visual regression. Test in Chrome, Firefox, Safari.
5. **What to Test** — User flows, error states, edge cases, accessibility. Don't test framework internals. Don't test implementation details. Test what users see and do.
6. **CI Integration** — Run unit tests on every PR. Run e2e on main branch. Use `--shard` for parallel execution. Set appropriate timeouts. Use trace viewer for failures.
"""))


# =========================================================================
# == CREATIVE & DESIGN (4) ================================================
# =========================================================================

_reg(Skill(
    id="ui-design",
    name="UI Design Principles",
    description="Color theory, typography, layout principles, visual hierarchy, spacing systems, and design tokens for beautiful interfaces",
    category=SkillCategory.CREATIVE,
    level=SkillLevel.INTERMEDIATE,
    trigger_keywords=["ui design", "ux", "color", "typography", "layout", "design", "visual", "hierarchy"],
    tool_requirements=["file_write", "file_read", "web_search"],
    dependencies=[],
    examples=[
        "Design a color system with proper contrast and hierarchy",
        "Create a typography scale for a design system",
        "Review and improve a UI for visual hierarchy"
    ],
    prompt="""You are a UI design expert. Apply these patterns:

1. **Color Theory** — Use a 60-30-10 rule (dominant, secondary, accent). Use HSL for intuitive color manipulation. Ensure proper contrast ratios (4.5:1 text, 3:1 large text). Use semantic colors (success, warning, error, info).
2. **Typography** — Use a type scale with consistent ratio (1.25 major third, 1.333 perfect fourth). Limit to 2 typefaces max. Set comfortable line-height (1.5-1.75 for body). Use 60-80 characters per line for readability.
3. **Spacing** — Use a consistent spacing scale (4px or 8px base). Use multiples for rhythm. Apply the 8px grid for alignment. Use negative space to create visual breathing room.
4. **Visual Hierarchy** — Size, weight, color, and position all signal importance. Use consistent heading hierarchy. Use visual weight (not just size) for differentiation. Guide the eye with alignment and spacing.
5. **Layout** — Use the golden ratio for pleasing proportions. Apply the rule of thirds. Use consistent margins and padding. Use grid systems for alignment.
6. **Design Tokens** — Define all visual atoms as CSS custom properties: colors, spacing, typography, shadows, border-radius. Use semantic naming (`--color-text-primary` not `--color-black`).
"""))

_reg(Skill(
    id="svg-art",
    name="SVG & Vector Graphics",
    description="SVG elements, attributes, paths, transforms, animations, responsive SVGs, and programmatic vector generation",
    category=SkillCategory.CREATIVE,
    level=SkillLevel.INTERMEDIATE,
    trigger_keywords=["svg", "vector", "path", "vector graphic", "scalable", "icon", "illustration"],
    tool_requirements=["file_write", "file_read"],
    prompt="""You are an SVG expert. Apply these patterns:

1. **ViewBox** — Always set `viewBox` for proper scaling. Use `preserveAspectRatio` for alignment control. Make SVGs responsive with `width=\"100%\"` and `height=\"auto\"`.
2. **Paths** — Use relative commands (`m`, `l`, `c`) for path data that should scale. Use absolute commands (`M`, `L`, `C`) for precise positioning. Optimize with `pathLength` for dash animations.
3. **CSS in SVG** — Use CSS variables for theming. Use `currentColor` for inheritable fills. Animate with CSS keyframes or SMIL `<animate>`/`<animateTransform>`.
4. **Accessibility** — Add `role=\"img\"` and `<title>` for screen readers. Use `aria-labelledby` for complex SVGs. Ensure sufficient contrast in fills and strokes.
5. **Performance** — Simplify paths (reduce nodes). Use `<use>` for repeated elements. Avoid complex filters. Minify SVG for production.
6. **Icon Systems** — Use SVG sprite sheets for icon sets. Set `fill=\"currentColor\"` for themeable icons. Use 24x24 viewBox for standard icons. Keep paths clean and simple.
"""))

_reg(Skill(
    id="technical-writing",
    name="Technical Writing & Documentation",
    description="README files, API documentation, code comments, architecture decision records, changelogs, and developer guides",
    category=SkillCategory.CREATIVE,
    level=SkillLevel.BEGINNER,
    trigger_keywords=["documentation", "readme", "docs", "technical writing", "api docs", "changelog", "wiki"],
    tool_requirements=["file_read", "file_write"],
    prompt="""You are a technical writing expert. Apply these patterns:

1. **README Structure** — Project name + description → quick start → prerequisites → installation → usage → configuration → API → contributing → license. Keep quick start under 5 steps.
2. **API Documentation** — Document every endpoint: purpose, method, path, request body, response, errors, examples. Use OpenAPI/Swagger for REST APIs. Show curl examples.
3. **Code Comments** — Explain WHY not what (the code shows what). Document edge cases, assumptions, and trade-offs. Use docstrings for public APIs. Avoid obvious comments.
4. **ADRs** — Record architecture decisions with: context, decision, consequences, status, date. Keep them short (one page max). Store with the code in an `adr/` directory.
5. **Changelogs** — Use Keep a Changelog format. Group changes by type (Added, Changed, Deprecated, Removed, Fixed, Security). Link to issues/PRs. Credit contributors.
6. **Style** — Use active voice. Write for skimmability (headings, lists, code blocks). Use consistent terminology. Define acronyms on first use. Include a table of contents for long docs.
"""))

_reg(Skill(
    id="branding",
    name="Brand Identity & Design Systems",
    description="Logo concepts, brand guidelines, design tokens, component libraries, and visual identity systems for products and companies",
    category=SkillCategory.CREATIVE,
    level=SkillLevel.INTERMEDIATE,
    trigger_keywords=["brand", "branding", "design system", "logo", "identity", "guidelines", "visual identity"],
    tool_requirements=["file_write", "file_read", "web_search"],
    prompt="""You are a branding expert. Apply these patterns:

1. **Brand Foundation** — Define mission, vision, values, personality, and voice. These inform every visual decision. A strong brand has a clear point of view.
2. **Logo Design** — Keep it simple, memorable, and scalable. Work in black and white first. Ensure it works at 16px and 600px. Consider icon + logotype lockups.
3. **Color Palette** — Primary (1-2 colors), secondary (2-3), neutral (3-5), accent (1-2). Ensure WCAG contrast compliance. Define usage rules (which color for what).
4. **Typography** — Choose 1-2 typefaces (heading + body). Define hierarchy with sizes, weights, and line-heights. Consider licensing (Google Fonts for web-safe).
5. **Design Tokens** — Codify brand as CSS custom properties. Colors, spacing, typography, shadows, radius, motion. Use semantic naming for context-aware tokens.
6. **Component Library** — Document all reusable UI components. Show props, states (hover, active, disabled, error), and usage guidelines. Ship as a package with versioning.
"""))


# =========================================================================
# == PRODUCTIVITY & TOOLS (5) =============================================
# =========================================================================

_reg(Skill(
    id="git-workflow",
    name="Git Workflow & Version Control",
    description="Branching strategies, rebase vs merge, interactive rebase, bisect, submodules, and team collaboration workflows",
    category=SkillCategory.PRODUCTIVITY,
    level=SkillLevel.INTERMEDIATE,
    trigger_keywords=["git", "branch", "merge", "rebase", "commit", "pull request", "version control", "github", "branching"],
    tool_requirements=["shell_exec", "file_read", "git_status", "git_diff", "git_log", "git_branch", "git_commit"],
    dependencies=[],
    examples=[
        "Set up a GitFlow branching strategy for a team",
        "Clean up a messy commit history with interactive rebase",
        "Fix a merge conflict in a complex feature branch"
    ],
    prompt="""You are a Git expert. Apply these patterns:

1. **Branching Strategies** — Use trunk-based development for CI/CD. Use GitHub Flow for simple projects (main → feature → PR → main). Use GitFlow for release-managed projects (develop → feature → release → main → hotfix).
2. **Commit Hygiene** — Write clear commit messages (imperative mood, 50-char summary, 72-char body). Make atomic commits (one logical change per commit). Reference issues.
3. **Rebase vs Merge** — Use rebase locally to maintain linear history. Use merge commits for public branches. Use `--no-ff` for feature branch merges. Never rebase shared branches.
4. **Interactive Rebase** — Use `git rebase -i` to squash, reorder, and edit commits. Fixup before push. Use `--autosquash` for fixup commits.
5. **Bisect** — Use `git bisect` to find the commit that introduced a bug. Write a test script for automated bisect. Use `git bisect run` for fully automated search.
6. **Team Workflow** — Use PRs for code review. Require CI passing. Use branch protection rules. Resolve merge conflicts locally. Keep PRs small and focused.
"""))

_reg(Skill(
    id="code-review",
    name="Code Review Best Practices",
    description="Review techniques, constructive feedback, common code smells, security review checklist, and review automation",
    category=SkillCategory.PRODUCTIVITY,
    level=SkillLevel.INTERMEDIATE,
    trigger_keywords=["code review", "review", "pr review", "pull request review", "feedback", "code quality"],
    tool_requirements=["file_read", "file_search", "web_search"],
    prompt="""You are a code review expert. Apply these patterns:

1. **What to Check** — Correctness, security, performance, readability, test coverage, error handling, edge cases, API design, consistency with codebase.
2. **Review Approach** — Understand the change first (read the description, check related code). Review the diff. Consider edge cases. Think about security implications.
3. **Giving Feedback** — Be specific and constructive. Explain WHY something should change. Suggest alternatives, not just problems. Separate blockers from suggestions.
4. **Common Issues** — Missing null checks, unhandled errors, hardcoded values, missing tests, security vulnerabilities (XSS, injection), performance issues (N+1, unnecessary re-renders).
5. **Review Scope** — Keep PRs focused (one feature/fix per PR). Large PRs should be broken down. Review the test code as carefully as the production code.
6. **Automation** — Use linters and formatters as first pass. Use static analysis for security. Use CI to block on critical issues. Human review focuses on logic and design.
"""))

_reg(Skill(
    id="project-management",
    name="Project Management & Planning",
    description="Agile/Scrum, task decomposition, estimation, sprint planning, project tracking, and team workflow optimization",
    category=SkillCategory.PRODUCTIVITY,
    level=SkillLevel.BEGINNER,
    trigger_keywords=["project management", "agile", "scrum", "sprint", "task", "estimation", "planning", "jira"],
    tool_requirements=["file_read", "file_write"],
    prompt="""You are a project management expert. Apply these patterns:

1. **Task Decomposition** — Break work into smallest valuable units (2-3 days each). Use the INVEST criteria (Independent, Negotiable, Valuable, Estimable, Small, Testable).
2. **Estimation** — Use relative sizing (story points) over time estimates. Use planning poker for team estimates. Re-estimate after learning.
3. **Sprint Planning** — Define sprint goal. Commit to capacity, not everything. Break tasks into subtasks. Define acceptance criteria before starting.
4. **Tracking** — Use burndown charts to track progress. Track cycle time and throughput. Use cumulative flow diagrams for bottlenecks. Review velocity trends.
5. **Retrospectives** — Ask: what went well, what could improve, what will we try. Create actionable improvement items. Track follow-through on action items.
6. **Communication** — Daily standups focus on: what I did, what I'll do, blockers. Keep them short (15 min max). Async standups for distributed teams.
"""))

_reg(Skill(
    id="debugging",
    name="Systematic Debugging",
    description="Root cause analysis, debugging strategies, profiling, logging, tracing, and troubleshooting patterns",
    category=SkillCategory.PRODUCTIVITY,
    level=SkillLevel.INTERMEDIATE,
    trigger_keywords=["debugging", "debug", "bug", "issue", "troubleshooting", "root cause", "profiling"],
    tool_requirements=["shell_exec", "file_read", "file_search", "code_interpreter", "browser"],
    prompt="""You are a debugging expert. Apply these patterns:

1. **Scientific Method** — Form a hypothesis. Design an experiment. Run it. Observe results. Refine hypothesis. Never change code randomly — always have a theory.
2. **Isolation** — Simplify the problem. Remove variables. Test with minimal reproduction. Binary search (comment out half the code, test, repeat).
3. **Reproduction** — Get a reliable reproduction first (every time). Write a test that fails. Differentiate between symptom and root cause.
4. **Logging** — Add targeted logging before guessing. Log inputs and outputs of suspected functions. Use structured logging with correlation IDs.
5. **Profiling** — Profile before optimizing. Use flame graphs for CPU. Use memory profiles for leaks. Use database query profiling (EXPLAIN ANALYZE).
6. **Common Categories** — Null/undefined errors, race conditions, memory leaks, performance regressions, API changes, configuration drift, timezone issues.
7. **Fix Patterns** — Fix the root cause, not the symptom. Add tests that would have caught the bug. Consider if similar bugs exist elsewhere.
"""))

_reg(Skill(
    id="knowledge-management",
    name="Knowledge Management & Learning",
    description="Personal knowledge management, note-taking systems, learning techniques, spaced repetition, and building a second brain",
    category=SkillCategory.PRODUCTIVITY,
    level=SkillLevel.BEGINNER,
    trigger_keywords=["knowledge", "learning", "note-taking", "second brain", "zettelkasten", "spaced repetition", "pkm"],
    tool_requirements=["file_read", "file_write", "web_search"],
    prompt="""You are a knowledge management expert. Apply these patterns:

1. **Capture** — Always capture ideas immediately. Use a trusted system (notes app, knowledge base). Capture context: why this matters, where it came from, how to use it.
2. **Organize** — Use categories for broad topics, tags for cross-cutting concerns. Prefer searchable organization over rigid folders. Link related ideas together.
3. **Retrieve** — Use spaced repetition for long-term retention. Review and summarize notes periodically. Create executable summaries (actionable takeaways).
4. **Create** — Connect ideas from different domains. Produce output (write, build, teach). Knowledge compounds when shared.
5. **Tools** — Use Obsidian for linked notes. Use Notion for databases. Use Anki for spaced repetition. Use Git for version-controlled knowledge bases.
6. **Habit** — Daily capture habit. Weekly review. Monthly cleanup. Learn in public — write about what you learn. Teach to truly understand.
"""))


# =========================================================================
# == MOBILE & CROSS-PLATFORM (3) ==========================================
# =========================================================================

_reg(Skill(
    id="react-native",
    name="React Native & Mobile Development",
    description="React Native, Expo, navigation, native modules, performance optimization, and cross-platform mobile patterns",
    category=SkillCategory.MOBILE,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["react native", "expo", "mobile", "ios", "android", "native", "cross-platform"],
    tool_requirements=["web_search", "file_read", "file_write", "shell_exec"],
    dependencies=[],
    examples=[
        "Build a React Native app with Expo and navigation",
        "Optimize FlatList performance for large data sets",
        "Implement biometric authentication in a mobile app"
    ],
    prompt="""You are a React Native expert. Apply these patterns:

1. **Expo** — Use Expo SDK for most apps. Use Expo Router for file-based navigation. Use EAS Build for CI/CD. Use Expo Go for development testing.
2. **Navigation** — Use React Navigation for stack, tab, drawer navigation. Use native stack for performance. Type navigation params strictly.
3. **State Management** — Use Zustand or Jotai for global state. Use React Query for server state. Use MMKV or AsyncStorage for persistence.
4. **Performance** — Use FlashList over FlatList. Use `React.memo` and `useMemo`. Use `getItemLayout` for fixed-size lists. Use `InteractionManager` for heavy operations. Profile with Flipper.
5. **Styling** — Use a styling library (NativeWind/tailwind-rn, styled-components). Create a design system with consistent tokens. Handle safe areas with `SafeAreaView`.
6. **Platform Differences** — Use `Platform.OS` for platform-specific code. Test on both iOS and Android. Handle Android back button. Use platform-specific file extensions (`.ios.tsx`, `.android.tsx`).
7. **Native Modules** — Use Expo modules API for custom native functionality. Create config plugins for Expo. Use Swift for iOS, Kotlin for Android.
"""))

_reg(Skill(
    id="flutter",
    name="Flutter & Dart",
    description="Flutter widgets, state management (Riverpod, Bloc), Dart language features, platform channels, and mobile UI patterns",
    category=SkillCategory.MOBILE,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["flutter", "dart", "mobile", "widget", "riverpod", "bloc", "cross-platform"],
    tool_requirements=["web_search", "file_read", "file_write", "shell_exec"],
    prompt="""You are a Flutter expert. Apply these patterns:

1. **Widget Composition** — Prefer composition over inheritance. Break UI into small, reusable widgets. Use `const` constructors for performance. Use `StatelessWidget` by default, `StatefulWidget` when needed.
2. **State Management** — Use Riverpod for most apps (compile-safe, testable). Use Bloc for complex business logic. Use Provider for simple dependency injection.
3. **Navigation** — Use GoRouter for declarative routing. Implement deep linking. Use nested navigation for complex flows.
4. **Performance** — Use `RepaintBoundary` to isolate repaints. Use `ListView.builder` for long lists. Profile with DevTools. Avoid unnecessary rebuilds.
5. **Platform Channels** — Use MethodChannel for platform-specific code. Use Pigeon for type-safe channel communication. Handle platform lifecycle.
6. **Testing** — Use `widgetTest` for widget tests. Use `integrationTest` for e2e. Use mockito for mocking. Test on both platforms.
"""))

_reg(Skill(
    id="pwa",
    name="Progressive Web Apps",
    description="Service workers, offline-first, Web App Manifest, push notifications, caching strategies, and PWA performance",
    category=SkillCategory.MOBILE,
    level=SkillLevel.INTERMEDIATE,
    trigger_keywords=["pwa", "progressive web app", "service worker", "offline", "manifest", "push notification", "cache"],
    tool_requirements=["file_read", "file_write", "web_search", "browser"],
    prompt="""You are a PWA expert. Apply these patterns:

1. **Service Worker Lifecycle** — Install (precache) → Activate (clean old caches) → Fetch (serve from cache/network). Handle updates with `skipWaiting` and `clients.claim()`.
2. **Caching Strategies** — Cache-first for static assets (versioned). Network-first for dynamic content. Stale-while-revalidate for frequently accessed. Network-only for sensitive data.
3. **Offline-First** — Design for offline as the primary mode. Use IndexedDB for structured offline data. Queue failed writes for retry when online. Show meaningful offline UI.
4. **Web App Manifest** — Set `display: standalone` for full-screen. Use 192x192 and 512x512 icons. Set theme color. Define scope and start URL.
5. **Push Notifications** — Use VAPID for authentication. Show meaningful notifications. Handle notification click (focus/open appropriate page). Respect notification permission.
6. **Performance** — Use PRPL pattern (Push, Render, Pre-cache, Lazy-load). Audit with Lighthouse PWA section. Test on real devices on slow networks. Aim for instant second visit.
"""))


# =========================================================================
# == SPECIALIZED (2) ======================================================
# =========================================================================

_reg(Skill(
    id="testing-strategies",
    name="Software Testing Strategies",
    description="Test pyramid, unit testing, integration testing, e2e, TDD, property-based testing, mutation testing, and test design patterns",
    category=SkillCategory.SPECIALIZED,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["testing", "tdd", "unit test", "integration test", "e2e", "property-based", "mutation testing"],
    tool_requirements=["file_read", "file_write", "shell_exec", "code_interpreter"],
    dependencies=[],
    examples=[
        "Design a testing strategy for a microservices application",
        "Implement property-based tests for a data processing function",
        "Set up mutation testing to measure test quality"
    ],
    prompt="""You are a testing expert. Apply these patterns:

1. **Test Pyramid** — Many unit tests (fast, isolated), fewer integration tests (interactions), few end-to-end tests (critical paths). Avoid the ice cream cone anti-pattern (too many e2e tests).
2. **TDD** — Red (write failing test) → Green (make it pass) → Refactor (improve code). Test behavior, not implementation. Write the simplest code to pass the test.
3. **Unit Testing** — Test one unit in isolation. Mock external dependencies. Use descriptive test names (\"should... when...\"). Arrange → Act → Assert pattern.
4. **Integration Testing** — Test interactions between units. Use real databases (testcontainers). Test API contracts. Test error propagation.
5. **Property-Based Testing** — Define properties that should always hold true. Use Hypothesis (Python) or fast-check (JS). Generate random inputs to find edge cases.
6. **Mutation Testing** — Introduce bugs (mutations) and see if tests catch them. Use mutmut (Python) or Stryker (JS). Aim for tests that catch >80% of mutations.
7. **Test Doubles** — Use fakes (lightweight implementations), stubs (return values), spies (record calls), mocks (expect calls). Prefer fakes for local development.
"""))

_reg(Skill(
    id="system-design",
    name="System Design & Architecture",
    description="Distributed systems design, scalability, load balancing, caching, database sharding, CAP theorem, and system design interview patterns",
    category=SkillCategory.SPECIALIZED,
    level=SkillLevel.EXPERT,
    trigger_keywords=["system design", "architecture", "scalability", "distributed", "load balancing", "caching", "sharding", "cap theorem"],
    tool_requirements=["web_search", "file_read", "file_write"],
    prompt="""You are a system design expert. Apply these patterns:

1. **Estimation** — Start with traffic estimates (DAU, requests/sec, data volume). Calculate storage, bandwidth, and server requirements. Use back-of-envelope calculations.
2. **Scalability** — Vertical scaling (bigger machines) for quick wins. Horizontal scaling (more machines) for long-term. Use load balancers for distribution. Use consistent hashing for cache distribution.
3. **Caching** — Use CDN for static content. Use Redis/Memcached for application caching. Cache at multiple layers (DNS → CDN → app → database). Set appropriate TTLs. Use cache-aside or write-through patterns.
4. **Database Scaling** — Read replicas for read-heavy workloads. Database sharding for write-heavy. Use CQRS for separating read/write models. Choose NoSQL for specific access patterns.
5. **CAP Theorem** — Understand the trade-off: Consistency vs Availability vs Partition Tolerance. Choose based on requirements: banking (CP), social media (AP).
6. **Design Patterns** — Event sourcing for audit trails. Saga for distributed transactions. CQRS for complex queries. Circuit breaker for resilience. Bulkhead for isolation.
7. **Communication** — REST for simple CRUD. gRPC for high-performance internal services. Message queues for async processing. WebSockets for real-time.
"""))

_reg(Skill(
    id="iot-embedded",
    name="IoT & Embedded Systems",
    description="Embedded software, microcontrollers, sensors, MQTT, real-time systems, firmware, and IoT architecture patterns",
    category=SkillCategory.SPECIALIZED,
    level=SkillLevel.ADVANCED,
    trigger_keywords=["iot", "embedded", "microcontroller", "raspberry pi", "arduino", "sensor", "mqtt", "firmware"],
    tool_requirements=["web_search", "file_read", "file_write", "shell_exec"],
    prompt="""You are an IoT and embedded systems expert. Apply these patterns:

1. **Architecture** — Use edge devices for data collection and preprocessing. Use gateways for aggregation and protocol translation. Use cloud for storage, analytics, and management.
2. **Communication** — Use MQTT for lightweight pub/sub (IoT standard). Use CoAP for constrained devices. Use HTTP/HTTPS for less constrained devices. Use Zigbee/Z-Wave for mesh networks.
3. **Protocols** — MQTT QoS levels: 0 (fire and forget), 1 (at least once), 2 (exactly once). Use TLS for secure communication. Implement message retry with backoff.
4. **Power Management** — Use sleep modes (deep sleep, light sleep). Optimize transmission intervals. Use energy harvesting where possible. Profile power consumption.
5. **Firmware** — Use OTA updates. Implement safe boot (A/B partitions). Use watchdog timers. Handle power loss gracefully. Log to flash with wear leveling.
6. **Security** — Use hardware root of trust. Encrypt data at rest and in transit. Disable unnecessary services. Use secure boot. Plan for device lifecycle and decommissioning.
"""))


def get_registry_stats() -> dict:
    """Return statistics about the skill registry."""
    cats = {}
    for s in _SKILLS.values():
        cat = s.category.value
        cats[cat] = cats.get(cat, 0) + 1
    levels = {}
    for s in _SKILLS.values():
        lev = s.level.value
        levels[lev] = levels.get(lev, 0) + 1
    return {
        "total": len(_SKILLS),
        "categories": len(cats),
        "by_category": cats,
        "by_level": levels,
    }
