// DOM role evidence, not size-based exemptions. Keep this function self-contained for page.evaluate.
export function classifyControlRoles(root = document) {
  const controls = 'button, select, textarea, input, .ant-select, .ant-picker, .ant-input-number, .ant-input-affix-wrapper, [role="button"], [role="tab"]';
  const selector = (el) => {
    const parts = [];
    for (let cur = el; cur && cur !== root.documentElement; cur = cur.parentElement) {
      const siblings = cur.parentElement ? [...cur.parentElement.children].filter((s) => s.tagName === cur.tagName) : [cur];
      parts.unshift(`${cur.tagName.toLowerCase()}:nth-of-type(${siblings.indexOf(cur) + 1})`);
    }
    return parts.join(' > ');
  };
  return [...root.querySelectorAll(controls)].map((el) => {
    let role = 'control', source = 'DESIGN.md §5.4 controls', reason = 'Input or standalone action';
    const header = el.parentElement;
    const sortState = header?.getAttribute('aria-sort');
    // A sole direct button carrying the complete sortable column label is the header's interaction.
    // A filter/export button elsewhere in a th, including a second button in a sortable th, is not.
    if (el.matches('button, [role="button"]') && header?.matches('th[scope="col"][aria-sort], [role="columnheader"][aria-sort]') && ['none', 'ascending', 'descending', 'other'].includes(sortState) && header.querySelectorAll('button, [role="button"]').length === 1 && el.textContent.trim() && el.textContent.trim() === header.textContent.trim()) {
      role = 'table-sort'; source = 'LedgerPnlDataTable.tsx: th[scope=col][aria-sort] > button'; reason = 'Sortable column label; DESIGN.md §5.4 table header 12/500';
    } else if (el.matches('[role="tab"]') || (el.matches('button.ledger-pnl-section-nav__item') && el.closest('nav.ledger-pnl-section-nav'))) {
      role = 'text-tab'; source = el.matches('[role="tab"]') ? 'DOM role=tab' : 'LedgerPnlSectionNav.tsx: nav.ledger-pnl-section-nav button.ledger-pnl-section-nav__item'; reason = 'Text tab or chapter navigation; DESIGN.md §3 and §5.4';
    } else if (el.matches('.kpi-card.kpi-card--clickable[role="button"]') && el.querySelector(':scope > .kpi-card__header .kpi-card__title') && el.querySelector(':scope > .kpi-card__body .kpi-card__value')) {
      role = 'clickable-card'; source = 'KpiCard.tsx: clickable root containing header/title and body/value'; reason = 'Whole content container; its text, decoration and nesting remain audited';
    } else if (el.matches('button.risk-tensor-brief__tile.risk-tensor-brief__tile--action') && el.parentElement?.matches('.risk-tensor-brief__tiles') && el.querySelector(':scope > strong') && el.querySelector(':scope > .risk-tensor-brief__tile-detail')) {
      role = 'clickable-card'; source = 'RiskTensorPage.tsx: brief tiles with label, strong value and detail'; reason = 'Whole content container; its text, decoration and nesting remain audited';
    } else if (el.matches('button[type="button"].market-data-series-library-entry[data-testid="market-data-series-library-entry"]') && el.parentElement?.matches('main.market-data-main[data-testid="market-data-main"]') && el.querySelector(':scope > .market-data-series-library-entry__titles > .market-data-series-library-entry__kicker')?.textContent.trim() && el.querySelector(':scope > .market-data-series-library-entry__titles > .market-data-series-library-entry__title')?.textContent.trim() && el.querySelector(':scope > .market-data-series-library-entry__meta')?.textContent.trim()) {
      role = 'clickable-card'; source = 'MarketDataPage.tsx: series library entry with title, kicker and availability summary'; reason = 'Whole content container; its text, decoration and nesting remain audited';
    } else if (el.matches('tr.ledger-pnl-data-table__row--clickable[role="button"]') && el.parentElement?.matches('tbody') && el.querySelectorAll(':scope > td').length > 1) {
      role = 'table-row'; source = 'LedgerPnlDataTable.tsx: clickable tbody tr with data cells'; reason = 'Data row; its height and cells use DESIGN.md §5.4 table checks';
    }
    return { selector: selector(el), id: el.id || null, role, source, reason };
  });
}

// Resolve identifiers from explicit value metadata or the column's visible label, never from
// digit count or current alignment. A left-aligned amount therefore remains an audit failure.
export function classifyTableValues(root = document) {
  const selector = (el) => {
    const parts = [];
    for (let cur = el; cur && cur !== root.documentElement; cur = cur.parentElement) {
      const siblings = cur.parentElement ? [...cur.parentElement.children].filter((s) => s.tagName === cur.tagName) : [cur];
      parts.unshift(`${cur.tagName.toLowerCase()}:nth-of-type(${siblings.indexOf(cur) + 1})`);
    }
    return parts.join(' > ');
  };
  const isNumber = (text) => /^[+\-−±]?[¥$€]?\d[\d,]*(\.\d+)?\s*(%|bp|bps|BP|pp|亿元|万元|亿|万|元|倍|x|X|年|个月|天|笔|只|户)?$/.test(text.replace(/\s+/g, ''));
  return [...root.querySelectorAll('tbody td, tfoot td, .ag-cell')].map((cell) => {
    const explicit = cell.closest('[data-moss-value-role]')?.getAttribute('data-moss-value-role');
    const numeric = cell.matches('[data-numeric="true"], .ledger-pnl-data-table__td--numeric, .moss-data-table__cell--numeric');
    let identifier = !numeric && (['id', 'code'].includes(explicit) || !!cell.querySelector('code, [data-moss-value-role="id"], [data-moss-value-role="code"]'));
    let source = identifier ? 'Explicit code/id DOM metadata' : 'Numeric text; no identifier evidence';
    if (!numeric && !identifier && cell.closest('table.ledger-pnl-data-table__table')) {
      const headers = [...cell.closest('table').querySelectorAll('thead > tr:last-child > th')];
      const header = headers[cell.cellIndex];
      if (header?.textContent.trim() === '科目代码') {
        identifier = true;
        source = 'LedgerPnlPage.tsx detailColumns account_code / 科目代码; LedgerPnlDataTable.tsx matching header column';
      }
    }
    return { selector: selector(cell), id: cell.id || null, role: identifier ? 'identifier' : 'quantity', requiresNumericAlignment: !identifier && isNumber(cell.textContent.trim()), source };
  });
}
