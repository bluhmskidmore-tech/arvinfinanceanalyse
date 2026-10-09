import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { evaluateCompliance, measureCompliance, parseArgs, validateConfig } from './visual-compliance-audit.mjs';
import { JSDOM } from 'jsdom';
import { classifyControlRoles, classifyTableValues } from './visual-compliance-control-roles.mjs';

const config = JSON.parse(readFileSync(new URL('./visual-compliance.thresholds.json', import.meta.url), 'utf8'));
const clean = () => ({ metrics: Object.fromEntries(Object.keys(config.rules).map((rule) => [rule, { value: 0, entries: [] }])) });

test('approved thresholds and the two required viewports are explicit', () => {
  assert.equal(validateConfig(config), config);
  assert.deepEqual(config.viewports.map(({ width, height }) => [width, height]), [[1440, 900], [1280, 720]]);
  assert.equal(config.routes.length, 21);
  assert.equal(config.rules['typography.boldPct'].max, 15);
  assert.equal(config.rules['typography.foldBoldPct'].max, 22);
  assert.equal(config.rules['containers.depth2'].max, 4);
  assert.deepEqual(config.measurements.fontSizes, [11, 12, 13, 14, 20, 24]);
});

test('every threshold is inclusive and each excess is a failure with selector evidence', () => {
  for (const [rule, { max }] of Object.entries(config.rules)) {
    const measurement = clean();
    measurement.metrics[rule] = { value: max, entries: [{ selector: '#target', value: max }] };
    assert.equal(evaluateCompliance(measurement, config).passed, true, `${rule} at maximum`);
    measurement.metrics[rule].value = max + 0.01;
    const result = evaluateCompliance(measurement, config);
    assert.equal(result.passed, false, `${rule} above maximum`);
    assert.equal(result.violations[0].rule, rule);
    assert.equal(result.violations[0].entries[0].selector, '#target');
  }
});

test('1280 scope keeps only overflow, truncation, left edge and control checks', () => {
  const measurement = clean();
  measurement.metrics['typography.boldPct'].value = 90;
  assert.equal(evaluateCompliance(measurement, config, 'minimum').passed, true);
  const rules = evaluateCompliance(measurement, config, 'minimum').checks.map(({ rule }) => rule);
  assert.deepEqual(rules, ['skeleton.leftEdgeRange', 'controls.geometry', 'controls.primaryPerGroup', 'stability.overflow', 'stability.truncation']);
  measurement.metrics['stability.truncation'].value = 1;
  assert.equal(evaluateCompliance(measurement, config, 'minimum').passed, false);
});

test('regression profile cannot claim full aesthetic acceptance', () => {
  const measurement = clean();
  measurement.metrics['typography.boldPct'].value = 90;
  assert.equal(evaluateCompliance(measurement, config, 'full', 'regression').passed, true);
  assert.equal(evaluateCompliance(measurement, config, 'full', 'regression').checks.length, 4);
  measurement.metrics['stability.jsErrors'].value = 1;
  assert.equal(evaluateCompliance(measurement, config, 'full', 'regression').passed, false);
  assert.equal(evaluateCompliance(measurement, config, 'minimum', 'regression').passed, false);
});

test('missing or invalid measurements fail closed', () => {
  const measurement = clean();
  delete measurement.metrics['numbers.nonTabular'];
  assert.throws(() => evaluateCompliance(measurement, config), /Missing or invalid measurement/);
  measurement.metrics['numbers.nonTabular'] = { value: NaN, entries: [] };
  assert.throws(() => evaluateCompliance(measurement, config), /Missing or invalid measurement/);
});

test('exceptions require traceable approval and cannot raise a threshold', () => {
  const withException = (entry) => ({ ...config, exceptions: [entry] });
  const exception = { route: '/ledger-pnl', rule: 'decoration.shadows', selectors: ['#test'], reason: 'Test fixture', approvedBy: 'PENDING' };
  assert.throws(() => validateConfig(withException(exception)), /recorded approver/);
  assert.throws(() => validateConfig(withException({ ...exception, approvedBy: 'Recorded approval', max: 3 })), /cannot replace thresholds/);
  assert.throws(() => validateConfig(withException({ ...exception, approvedBy: 'Recorded approval', rule: 'unknown' })), /Unknown exception rule/);
});

test('CLI defaults to all routes and rejects malformed options', () => {
  assert.deepEqual(parseArgs([]).routes, []);
  assert.deepEqual(parseArgs(['--out', 'test-output', '/ledger-pnl']).routes, ['/ledger-pnl']);
  assert.throws(() => parseArgs(['--out']), /Missing value/);
  assert.throws(() => parseArgs(['--profile', 'accept-anything']), /profile must/);
  assert.throws(() => parseArgs(['--report-only']), /Unknown argument/);
  assert.throws(() => parseArgs(['--base', 'file:///tmp']), /HTTP/);
});

const roleMap = (markup) => {
  const dom = new JSDOM(markup);
  const roles = Object.fromEntries(classifyControlRoles(dom.window.document).filter((entry) => entry.id).map((entry) => [entry.id, entry.role]));
  dom.window.close();
  return roles;
};

test('sortable column labels use the table role, unrelated th controls retain control geometry', () => {
  assert.deepEqual(roleMap(`<table><thead><tr>
    <th scope="col" aria-sort="none"><button id="sort"><span>PnL</span><span aria-hidden="true"></span></button></th>
    <th scope="col"><button id="export">Export</button></th>
    <th scope="col" aria-sort="ascending">Balance <button id="filter">Filter</button></th>
    <th scope="col" aria-sort="none"><button id="sortWithFilter">Name</button><button id="secondFilter">Filter</button></th>
    <th scope="col" aria-sort="none"><input id="input" aria-label="Filter"></th>
  </tr></thead></table>`), { sort: 'table-sort', export: 'control', filter: 'control', sortWithFilter: 'control', secondFilter: 'control', input: 'control' });
});

test('text tabs require an explicit tab role or the verified chapter-navigation component', () => {
  assert.deepEqual(roleMap(`<nav class="ledger-pnl-section-nav">
    <button id="chapter" class="ledger-pnl-section-nav__item"><span>Summary</span></button>
    <button id="navExport">Export</button></nav>
    <div role="tablist"><button id="tab" role="tab">History</button><button id="toolbarAction">Add</button></div>
    <button id="orphanClass" class="ledger-pnl-section-nav__item">Action</button>`), { chapter: 'text-tab', navExport: 'control', tab: 'text-tab', toolbarAction: 'control', orphanClass: 'control' });
});

test('only the complete KpiCard root is a clickable container; actions inside it stay controls', () => {
  assert.deepEqual(roleMap(`<div id="kpi" class="kpi-card kpi-card--clickable" role="button">
    <div class="kpi-card__header"><div class="kpi-card__title">PnL</div></div>
    <div class="kpi-card__body"><span class="kpi-card__value">100</span><button id="cardAction">Details</button></div>
  </div><div id="incompleteCard" class="kpi-card kpi-card--clickable" role="button">Action</div>`), { kpi: 'clickable-card', cardAction: 'control', incompleteCard: 'control' });
});

test('risk-tensor tiles require the verified parent, value and detail structure', () => {
  assert.deepEqual(roleMap(`<div class="risk-tensor-brief__tiles">
    <button id="tile" class="risk-tensor-brief__tile risk-tensor-brief__tile--action"><span>Tenor</span><strong>5Y</strong><span class="risk-tensor-brief__tile-detail">KRD</span></button>
    <button id="incompleteTile" class="risk-tensor-brief__tile risk-tensor-brief__tile--action">Retry</button>
    <button id="largeButton" style="height:160px">Run</button>
  </div>`), { tile: 'clickable-card', incompleteTile: 'control', largeButton: 'control' });
});

const marketEntry = (id, { title = 'Macro and FX', meta = 'Stable 0; degraded 0', kicker = 'More readings', type = 'button' } = {}) => `
  <button id="${id}" type="${type}" class="market-data-series-library-entry" data-testid="market-data-series-library-entry">
    <span class="market-data-series-library-entry__titles">
      <span class="market-data-series-library-entry__kicker">${kicker}</span>
      <span class="market-data-series-library-entry__title">${title}</span>
    </span><span class="market-data-series-library-entry__meta">${meta}</span>
  </button>`;

test('only the complete market library content entry uses the card role; ordinary and incomplete controls remain controls', () => {
  assert.deepEqual(roleMap(`<main class="market-data-main" data-testid="market-data-main">
    ${marketEntry('library')}${marketEntry('missingTitle', { title: '' })}
    ${marketEntry('missingMeta', { meta: '' })}${marketEntry('missingKicker', { kicker: '' })}
    ${marketEntry('submit', { type: 'submit' })}
    <button id="sameClass" type="button" class="market-data-series-library-entry">Retry</button>
    <button id="ordinary">Refresh</button><select id="select"><option>2026</option></select>
  </main><div>${marketEntry('wrongParent')}</div>`), {
    library: 'clickable-card', missingTitle: 'control', missingMeta: 'control', missingKicker: 'control',
    submit: 'control', sameClass: 'control', ordinary: 'control', select: 'control', wrongParent: 'control',
  });
});

test('selected and unselected owner rows remain selection controls regardless of icon or height', () => {
  assert.deepEqual(roleMap(`<section class="kpi-owner-list-card" data-testid="kpi-owner-list-panel">
    <div id="selectedOwner" class="kpi-owner-list__row kpi-owner-list__row--selected" role="button" aria-pressed="true">
      <div class="kpi-owner-list__row-content"><div class="kpi-owner-list__avatar">Icon</div><span class="kpi-owner-list__name">Owner A</span></div>
    </div><div id="owner" class="kpi-owner-list__row" role="button" aria-pressed="false" style="height:160px">
      <div class="kpi-owner-list__row-content"><div class="kpi-owner-list__avatar">Icon</div><span class="kpi-owner-list__name">Owner B</span></div>
    </div></section>`), { selectedOwner: 'control', owner: 'control' });
});

test('card classification retains content and container checks while incomplete buttons and selects retain geometry checks', () => {
  // JSDOM has no layout engine. Supply only rectangles and visibility; execute the
  // production measurement against its DOM and computed CSS, without a copied audit.
  const dom = new JSDOM(`<style>
    * { color: rgb(0, 0, 0); background-color: rgb(255, 255, 255); font-size: 13px; font-weight: 400;
      border: 0px solid rgb(0, 0, 0); border-top-left-radius: 8px; border-top-right-radius: 8px;
      border-bottom-left-radius: 8px; border-bottom-right-radius: 8px; box-shadow: none; }
    #library { border: 1px solid rgb(0, 0, 0); box-shadow: 0px 1px 4px rgb(0, 0, 0); }
    #library .market-data-series-library-entry__title { font-size: 16px; }
    #incomplete, #ordinary, #select { font-size: 16px; }
  </style><div data-testid="workbench-main-content"><section id="outer"><section id="inner">
    <main class="market-data-main" data-testid="market-data-main">${marketEntry('library')}
      <button id="incomplete" type="button" class="market-data-series-library-entry" data-testid="market-data-series-library-entry">Retry</button>
      <button id="ordinary">Refresh</button><select id="select"><option>2026</option></select>
    </main></section></section></div>`, { runScripts: 'outside-only' });
  try {
    dom.window.HTMLElement.prototype.getBoundingClientRect = function () { return new dom.window.DOMRect(0, 0, 640, 58); };
    dom.window.HTMLElement.prototype.checkVisibility = () => true;
    dom.window.CSS = { escape: (value) => value }; // All fixture IDs are simple CSS identifiers.
    const controlRoles = classifyControlRoles(dom.window.document);
    const measure = dom.window.eval(`(${measureCompliance.toString()})`);
    const measurement = measure({ config, route: '/market-data', controlRoles, tableValueRoles: [], legacy: {
      mainInnerW: 640, evidence: { shellFrames: [], pageFrames: [], boxes: [
        { selector: '#outer', depth: 1, w: 640, top: 0 }, { selector: '#inner', depth: 2, w: 640, top: 0 },
      ] },
    } });
    const geometry = measurement.metrics['controls.geometry'].entries.map(({ selector }) => selector);
    for (const id of ['incomplete', 'ordinary', 'select']) assert.ok(geometry.includes(`#${id}`), `${id} retains geometry`);
    assert.equal(geometry.includes('#library'), false);
    assert.ok(measurement.metrics['typography.sizes'].entries.some(({ selector }) => selector.startsWith('#library >')));
    assert.ok(measurement.metrics['decoration.shadows'].entries.some(({ selector }) => selector === '#library'));
    assert.ok(measurement.metrics['containers.depth3'].entries.some(({ selector }) => selector === '#library'));
    assert.equal(evaluateCompliance(measurement, config).passed, false);
  } finally {
    dom.window.close();
  }
});

test('clickable ledger data rows keep table rules while buttons in cells retain control rules', () => {
  assert.deepEqual(roleMap(`<table><tbody><tr id="row" role="button" class="ledger-pnl-data-table__row--clickable">
    <td>Account</td><td>100</td><td><button id="rowAction">Export</button></td>
  </tr></tbody></table><div id="pretendRow" role="button" class="ledger-pnl-data-table__row--clickable">Retry</div>`), { row: 'table-row', rowAction: 'control', pretendRow: 'control' });
});

test('account code columns are identifiers but left-aligned amounts and counts still require right alignment', () => {
  const dom = new JSDOM(`<table class="ledger-pnl-data-table__table"><thead><tr>
    <th><button>科目代码<span aria-hidden="true"></span></button></th><th>期末余额</th><th>笔数</th>
  </tr></thead><tbody><tr>
    <td id="account" style="text-align:left">514100</td>
    <td id="amount" style="text-align:left" class="ledger-pnl-data-table__td--numeric">514100</td>
    <td id="count" style="text-align:left">4</td>
  </tr></tbody></table><table><tbody><tr><td id="unknown" style="text-align:left">514100</td>
    <td id="explicitId" data-moss-value-role="id">12345</td></tr></tbody></table>`);
  const values = Object.fromEntries(classifyTableValues(dom.window.document).map((record) => [record.id, record]));
  assert.equal(values.account.role, 'identifier');
  assert.equal(values.account.requiresNumericAlignment, false);
  assert.equal(values.explicitId.requiresNumericAlignment, false);
  for (const id of ['amount', 'count', 'unknown']) {
    assert.equal(values[id].requiresNumericAlignment, true, `${id} must not inherit an identifier exemption`);
    assert.equal(dom.window.getComputedStyle(dom.window.document.getElementById(id)).textAlign, 'left');
  }
  dom.window.close();
});
