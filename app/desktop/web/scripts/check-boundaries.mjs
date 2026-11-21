import { readdirSync, readFileSync, writeFileSync, unlinkSync } from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
function files(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const path = join(directory, entry.name)
    return entry.isDirectory() ? files(path) : /\.(?:ts|cts|vue)$/.test(path) && !path.endsWith('.test.ts') ? [path] : []
  })
}
function owner(path) {
  const local = relative(root, path).replaceAll('\\', '/')
  if (local === 'bridge.ts' || local === 'bridge.js' || local === 'bridge') return 'bridge'
  if (local.startsWith('electron/')) return 'electron'
  if (local.startsWith('src/features/')) return local.split('/').slice(0, 3).join('/')
  if (local.startsWith('src/components/ui/')) return 'ui'
  if (local.startsWith('src/connection/')) return 'connection'
  if (local.startsWith('src/app/')) return 'app'
  return 'unknown'
}
function check() {
  const errors = []
  for (const file of [...files(join(root, 'src')), ...files(join(root, 'electron')), join(root, 'bridge.ts')]) {
    let text = readFileSync(file, 'utf8')
    if (file.endsWith('.vue')) text = text.match(/<script\b[^>]*>([\s\S]*?)<\/script>/)?.[1] || ''
    const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true)
    const from = owner(file)
    function inspect(specifier) {
      if (!ts.isStringLiteral(specifier)) { errors.push(`${file}: dynamic imports must be literal`); return }
      const name = specifier.text
      if (!name.startsWith('.') && !name.startsWith('@/')) {
        if (from !== 'electron' && (name === 'electron' || name.startsWith('node:'))) errors.push(`${file}: forbidden platform import ${name}`)
        return
      }
      const target = name.startsWith('@/') ? resolve(root, 'src', name.slice(2)) : resolve(dirname(file), name)
      const to = owner(target)
      const allowed = to === from || to === 'bridge' || from === 'app' && (to === 'connection' || to.startsWith('src/features/') || to === 'ui')
        || from.startsWith('src/features/') && to === 'ui'
      if (!allowed) errors.push(`${file}: forbidden dependency ${from} -> ${to}`)
      if (from === 'app' && to.startsWith('src/features/') && relative(root, target).split('/').length > 3
        && !/[/]index(?:\.[jt]s)?$/.test(target)) errors.push(`${file}: feature imports must use public entry points`)
    }
    function visit(node) {
      if ((ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) && node.moduleSpecifier) inspect(node.moduleSpecifier)
      if (ts.isCallExpression(node) && (node.expression.kind === ts.SyntaxKind.ImportKeyword
        || ts.isIdentifier(node.expression) && node.expression.text === 'require')) {
        if (node.arguments[0]) inspect(node.arguments[0])
        else errors.push(`${file}: missing dynamic import target`)
      }
      ts.forEachChild(node, visit)
    }
    visit(source)
  }
  return errors
}

if (process.argv.includes('--self-test')) {
  const probe = join(root, 'src/features/manual/boundary-probe.ts')
  try {
    writeFileSync(probe, "import '../workspace'\n", { flag: 'wx' })
    if (!check().some(error => error.includes('boundary-probe.ts'))) throw new Error('Forbidden feature dependency was not detected')
  } finally { unlinkSync(probe) }
}
const errors = check()
if (errors.length) { console.error(errors.join('\n')); process.exit(1) }
console.log('Desktop module boundaries passed.')
