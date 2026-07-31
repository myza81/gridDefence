/**
 * Authenticated visual-preview harness (Phase D §18) — DEV/SCREENSHOT ONLY.
 *
 * This is NOT part of the product. It renders the REAL Application Shell V2 and
 * real Engineering Home as a signed-in engineer by seeding a session token and
 * stubbing only the IAM calls AuthProvider makes — the same idea as
 * tests/authFixture.tsx, reused for a browser. It replaces Phase C's temporary
 * unguarded-route workaround: production routing (src/app/router.tsx) is never
 * modified to take screenshots.
 *
 * Usage:
 *   npm run dev   →  open  http://localhost:5173/shell-preview.html
 *                    ?route=/substations   to preview a specific location
 *                    ?page=home            to force the Engineering Home
 * Not referenced by index.html, so `vite build` never bundles it.
 */
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { AppShell } from "../src/components/layout/AppShell";
import { AuthProvider } from "../src/modules/iam/AuthContext";
import { EngineeringHomePage } from "../src/modules/home/pages/EngineeringHomePage";
import { resolveBreadcrumbs } from "../src/app/breadcrumbs";
import { authStorage } from "../src/modules/iam/authStorage";
import { tokens } from "../src/theme/tokens";

const PREVIEW_USER = {
  user_id: "preview-0000-0000-0000-000000000001",
  username: "sfong",
  display_name: "Su Fong",
  email: "su.fong@example.gov",
  status: "active",
};

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
}

// Stub only the IAM session calls; anything else falls through to the network.
const realFetch = window.fetch.bind(window);
window.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
  const url = typeof input === "string" ? input : input.toString();
  if (/\/api\/v1\/users\/me$/.test(url)) return Promise.resolve(jsonResponse(PREVIEW_USER));
  if (/\/api\/v1\/users\/[^/]+\/roles$/.test(url)) return Promise.resolve(jsonResponse([]));
  if (/\/api\/v1\/auth\/logout$/.test(url)) return Promise.resolve(jsonResponse(null));
  return realFetch(input as RequestInfo, init);
}) as typeof window.fetch;

authStorage.setToken("preview-session-token", false);

const params = new URLSearchParams(window.location.search);
const route = params.get("page") === "home" ? "/" : params.get("route") ?? "/";

/** A believable, data-free workspace so non-root routes show active nav + crumbs. */
function PreviewWorkspace({ pathname }: { pathname: string }) {
  const crumbs = resolveBreadcrumbs(pathname);
  const title = crumbs[crumbs.length - 1]?.label ?? "Workspace";
  return (
    <div style={{ maxWidth: "1200px", margin: "0 auto", fontFamily: tokens.typography.fontFamily, color: tokens.color.textPrimary }}>
      <h1 style={{ margin: "0 0 6px", fontSize: "19px" }}>{title}</h1>
      <p style={{ margin: "0 0 16px", color: tokens.color.textSecondary, fontSize: "13px" }}>
        Preview placeholder for <code>{pathname}</code> — the real workspace renders here inside the shell.
      </p>
      <div
        style={{
          background: tokens.color.surfacePanel,
          border: `1px solid ${tokens.color.borderDefault}`,
          borderRadius: tokens.radius.lg,
          boxShadow: tokens.shadow.hairline,
          padding: "20px",
          minHeight: "260px",
        }}
      />
    </div>
  );
}

function PreviewPage() {
  return route === "/" ? <EngineeringHomePage /> : <PreviewWorkspace pathname={route} />;
}

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route
              path="*"
              element={
                <AppShell>
                  <PreviewPage />
                </AppShell>
              }
            />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
);

// Layout-overflow measurement for headless verification (read via document.title).
window.setTimeout(() => {
  const el = document.documentElement;
  document.title = `sw=${el.scrollWidth} cw=${el.clientWidth} sh=${el.scrollHeight} ch=${el.clientHeight}`;
}, 600);
