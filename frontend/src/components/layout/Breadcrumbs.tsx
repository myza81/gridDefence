import { Fragment } from "react";
import { Link, useLocation } from "react-router-dom";

import { resolveBreadcrumbs } from "../../app/breadcrumbs";
import { tokens } from "../../theme/tokens";

/**
 * Orientation trail for the current location (Navigation Architecture §9),
 * derived from the shared navigation taxonomy — never hand-authored per page.
 * The final crumb is the current page and is not a link (aria-current="page").
 */
export function Breadcrumbs() {
  const { pathname } = useLocation();
  const crumbs = resolveBreadcrumbs(pathname);

  return (
    <nav aria-label="Breadcrumb" style={{ display: "flex", minWidth: 0 }}>
      <ol
        style={{
          display: "flex",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "6px",
          listStyle: "none",
          margin: 0,
          padding: 0,
          fontFamily: tokens.typography.fontFamily,
          fontSize: "12.5px",
          color: tokens.color.textSecondary,
        }}
      >
        {crumbs.map((crumb, index) => {
          const isLast = index === crumbs.length - 1;
          return (
            <Fragment key={`${crumb.label}-${index}`}>
              {index > 0 && (
                <li aria-hidden="true" style={{ color: tokens.color.textFaint }}>
                  /
                </li>
              )}
              <li style={{ display: "flex" }}>
                {crumb.to && !isLast ? (
                  <Link to={crumb.to} style={{ color: tokens.color.textSecondary, textDecoration: "none" }}>
                    {crumb.label}
                  </Link>
                ) : (
                  <span
                    aria-current={isLast ? "page" : undefined}
                    style={{ color: isLast ? tokens.color.textPrimary : tokens.color.textSecondary, fontWeight: isLast ? tokens.typography.weight.semibold : tokens.typography.weight.regular }}
                  >
                    {crumb.label}
                  </span>
                )}
              </li>
            </Fragment>
          );
        })}
      </ol>
    </nav>
  );
}
