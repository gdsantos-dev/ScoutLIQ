// One-time, reviewable migration. Run against the extracted 1.35 source only.
const fs = require('node:fs');
const path = require('node:path');
const postcss = require('../frontend/node_modules/postcss');
const root = path.resolve(__dirname, '..');
if (JSON.parse(fs.readFileSync(path.join(root, 'frontend/package.json'), 'utf8')).version !== '1.35.0') throw new Error('One-time migration: use only the extracted v1.35 baseline.');
const removed = [];
const shell = /\.(product-shell|workspace-masthead|workspace-brand|workspace-menu-trigger|workspace-menu|workspace-identity|environment-switch|environment-dot|workspace-utilities|workspace-navigation|environment-caption|context-navigation|workspace-date|command-trigger|nav-label-desktop|nav-label-mobile)(?![\w-])/;
for (const file of ['styles.css', 'workspace.css']) {
  const location = path.join(root, 'frontend/src', file);
  const ast = postcss.parse(fs.readFileSync(location, 'utf8'));
  ast.walkRules(rule => {
    if (rule.selector === ':root' && file === 'workspace.css') {
      removed.push({ file, line: rule.source.start.line, selector: rule.selector, reason: 'tokens now have one owner' });
      rule.remove(); return;
    }
    const keep = rule.selectors.filter(selector => {
      if (!shell.test(selector)) return true;
      removed.push({ file, line: rule.source.start.line, selector, reason: 'WorkspaceShell.module.css owns this surface' });
      return false;
    });
    if (!keep.length) rule.remove(); else rule.selectors = keep;
  });
  // Exact duplicates in the same parent only: retain the last occurrence.
  function dedupe(parent) {
    const seen = new Set();
    [...(parent.nodes || [])].reverse().forEach(node => {
      if (node.nodes) dedupe(node);
      if (node.type !== 'rule') return;
      const signature = node.toString().replace(/\s+/g, ' ').trim();
      if (seen.has(signature)) { removed.push({ file, selector: node.selector, reason: 'identical rule in same scope' }); node.remove(); }
      else seen.add(signature);
    });
  }
  dedupe(ast);
  ast.walkAtRules(rule => { if (rule.nodes && !rule.nodes.length) rule.remove(); });
  fs.writeFileSync(location, ast.toString());
}
fs.mkdirSync(path.join(root,'artifacts'), {recursive:true});
fs.writeFileSync(path.join(root,'artifacts/css-consolidation.json'),JSON.stringify(removed,null,2));
console.log(`${removed.length} obsolete/duplicate selectors removed; retained unrelated page rules.`);
