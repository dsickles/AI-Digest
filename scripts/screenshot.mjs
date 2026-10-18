/**
 * Capture a PNG of a page with Chrome or Chromium already on the machine.
 *
 * Usage:
 *   node scripts/screenshot.mjs <url> <outPath> [--width 1280] [--height 800] [--full-page]
 *
 * Chrome is resolved once, in this order:
 *   1. CHROME_PATH
 *   2. Puppeteer cache, then Playwright cache, when either is installed
 *   3. google-chrome, google-chrome-stable, chromium, chromium-browser on PATH
 *   4. the macOS Google Chrome app
 */
import { createRequire } from 'node:module';
import { accessSync, constants, existsSync, mkdirSync, readdirSync, realpathSync, statSync } from 'node:fs';
import { homedir } from 'node:os';
import { basename, delimiter, dirname, join, resolve } from 'node:path';
import puppeteer from 'puppeteer-core';

const require = createRequire(import.meta.url);

const USAGE =
  'Usage: node scripts/screenshot.mjs <url> <outPath> [--width 1280] [--height 800] [--full-page]';

const DEFAULT_WIDTH = 1280;
const DEFAULT_HEIGHT = 800;
const MAC_CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PATH_BROWSERS = ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'];

const EXECUTABLE_NAMES = [
  'chrome',
  'chrome.exe',
  'chromium',
  'chromium.exe',
  'google-chrome',
  'google-chrome-stable',
  'Google Chrome',
  'Google Chrome for Testing',
  'Chromium',
  'headless_shell',
  'headless_shell.exe',
  'chrome-headless-shell',
  'chrome-headless-shell.exe',
];

const EXECUTABLE_RANK = new Map(EXECUTABLE_NAMES.map((name, index) => [name, index]));

function packageJsonPath(specifier) {
  try {
    return require.resolve(`${specifier}/package.json`);
  } catch {
    return null;
  }
}

function isExecutable(filePath) {
  try {
    if (!statSync(filePath).isFile()) return false;
    if (process.platform === 'win32') return true;
    accessSync(filePath, constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

function which(command) {
  const pathEnv = process.env.PATH ?? '';
  const extensions =
    process.platform === 'win32' ? (process.env.PATHEXT || '.EXE;.CMD;.BAT').split(';').filter(Boolean) : [''];
  for (const dir of pathEnv.split(delimiter)) {
    if (!dir) continue;
    for (const ext of extensions) {
      const candidate = join(dir, ext ? command + ext : command);
      if (isExecutable(candidate)) return candidate;
    }
  }
  return null;
}

function findNamedExecutables(root) {
  if (!root || !existsSync(root)) return [];
  const wanted = new Set(EXECUTABLE_NAMES);
  const found = [];
  const seen = new Set();

  function walk(dir, depth) {
    let real;
    try {
      real = realpathSync(dir);
    } catch {
      return;
    }
    if (seen.has(real)) return;
    seen.add(real);

    let entries;
    try {
      entries = readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }

    for (const entry of entries) {
      if (entry.name === 'node_modules' || entry.name === '.git') continue;
      const full = join(dir, entry.name);
      let info;
      try {
        info = statSync(full);
      } catch {
        continue;
      }
      if (info.isDirectory()) {
        if (depth < 8) walk(full, depth + 1);
        continue;
      }
      if (info.isFile() && wanted.has(entry.name) && isExecutable(full)) found.push(full);
    }
  }

  walk(root, 0);
  return found;
}

function pickExecutable(paths) {
  let best = null;
  for (const filePath of paths) {
    const rank = EXECUTABLE_RANK.get(basename(filePath)) ?? 99;
    let mtimeMs = 0;
    try {
      mtimeMs = statSync(filePath).mtimeMs;
    } catch {
      continue;
    }
    if (!best || rank < best.rank || (rank === best.rank && mtimeMs > best.mtimeMs)) {
      best = { filePath, rank, mtimeMs };
    }
  }
  return best?.filePath ?? null;
}

function firstInstalled(dirs, via) {
  const found = pickExecutable(dirs.flatMap((dir) => findNamedExecutables(dir)));
  return found ? { path: found, via } : null;
}

async function executableFromModule(specifier, readPath) {
  if (!packageJsonPath(specifier)) return null;
  try {
    const loaded = await import(specifier);
    const reader = readPath(loaded);
    if (typeof reader !== 'function') return null;
    const result = reader();
    const executablePath = await result;
    if (typeof executablePath === 'string' && isExecutable(executablePath)) return executablePath;
  } catch {
    return null;
  }
  return null;
}

function puppeteerCacheDirs() {
  const dirs = [];
  if (process.env.PUPPETEER_CACHE_DIR) dirs.push(process.env.PUPPETEER_CACHE_DIR);
  dirs.push(join(homedir(), '.cache', 'puppeteer'));
  if (process.platform === 'darwin') dirs.push(join(homedir(), 'Library', 'Caches', 'puppeteer'));
  if (process.platform === 'win32' && process.env.LOCALAPPDATA) {
    dirs.push(join(process.env.LOCALAPPDATA, 'puppeteer'));
  }
  return dirs;
}

function playwrightCacheDirs() {
  const dirs = [];
  const fromEnv = process.env.PLAYWRIGHT_BROWSERS_PATH;
  if (fromEnv && fromEnv !== '0') dirs.push(fromEnv);
  dirs.push(join(homedir(), '.cache', 'ms-playwright'));
  if (process.platform === 'darwin') dirs.push(join(homedir(), 'Library', 'Caches', 'ms-playwright'));
  if (process.platform === 'win32' && process.env.LOCALAPPDATA) {
    dirs.push(join(process.env.LOCALAPPDATA, 'ms-playwright'));
  }
  for (const specifier of ['playwright-core', 'playwright', '@playwright/test']) {
    const pkg = packageJsonPath(specifier);
    if (!pkg) continue;
    dirs.push(join(dirname(pkg), '.local-browsers'));
  }
  return dirs;
}

async function findPuppeteerChrome() {
  const fromPackage = await executableFromModule('puppeteer', (loaded) => loaded.executablePath ?? loaded.default?.executablePath);
  if (fromPackage) return { path: fromPackage, via: 'Puppeteer cache' };
  return firstInstalled(puppeteerCacheDirs(), 'Puppeteer cache');
}

async function findPlaywrightChrome() {
  for (const specifier of ['playwright', 'playwright-core', '@playwright/test']) {
    const fromPackage = await executableFromModule(specifier, (loaded) => {
      const chromium = loaded.chromium ?? loaded.default?.chromium;
      return chromium?.executablePath?.bind(chromium);
    });
    if (fromPackage) return { path: fromPackage, via: 'Playwright cache' };
  }
  return firstInstalled(playwrightCacheDirs(), 'Playwright cache');
}

async function findChrome() {
  const fromEnv = process.env.CHROME_PATH;
  if (fromEnv) {
    if (!isExecutable(fromEnv)) {
      throw new Error(
        [
          `CHROME_PATH is set to ${fromEnv}, but that is not an executable file.`,
          'Set CHROME_PATH to the Chrome or Chromium binary.',
          'Example: CHROME_PATH=/usr/bin/google-chrome node scripts/screenshot.mjs <url> <outPath>',
        ].join('\n'),
      );
    }
    return { path: fromEnv, via: 'CHROME_PATH' };
  }

  const fromPuppeteer = await findPuppeteerChrome();
  if (fromPuppeteer) return fromPuppeteer;

  const fromPlaywright = await findPlaywrightChrome();
  if (fromPlaywright) return fromPlaywright;

  for (const name of PATH_BROWSERS) {
    const found = which(name);
    if (found) return { path: found, via: `PATH (${name})` };
  }

  if (isExecutable(MAC_CHROME)) return { path: MAC_CHROME, via: 'macOS app' };

  throw new Error(
    [
      'Chrome was not found.',
      'Set CHROME_PATH to the Chrome or Chromium binary, then rerun the command.',
      'Example: CHROME_PATH=/usr/bin/google-chrome node scripts/screenshot.mjs <url> <outPath>',
      'Searched CHROME_PATH, the Puppeteer cache, the Playwright cache, google-chrome, google-chrome-stable, chromium, and chromium-browser on PATH, and /Applications/Google Chrome.app/Contents/MacOS/Google Chrome.',
    ].join('\n'),
  );
}

function takeValue(argv, index, flag) {
  const token = argv[index];
  const eq = token.indexOf('=');
  if (eq !== -1) {
    const value = token.slice(eq + 1);
    if (!value) throw new Error(`Missing value for ${flag}.\n${USAGE}`);
    return { value, index };
  }
  const value = argv[index + 1];
  if (value === undefined || value.startsWith('--')) throw new Error(`Missing value for ${flag}.\n${USAGE}`);
  return { value, index: index + 1 };
}

function parseArgs(argv) {
  if (argv.includes('--help') || argv.includes('-h')) {
    console.log(USAGE);
    process.exit(0);
  }

  const positional = [];
  let width = DEFAULT_WIDTH;
  let height = DEFAULT_HEIGHT;
  let fullPage = false;

  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--full-page') {
      fullPage = true;
      continue;
    }
    const flag = arg.startsWith('--') ? arg.split('=')[0] : null;
    if (flag === '--width' || flag === '--height') {
      const taken = takeValue(argv, i, flag);
      i = taken.index;
      const parsed = Number(taken.value);
      if (!Number.isInteger(parsed) || parsed < 1) {
        throw new Error(`${flag} must be a positive integer. Got ${taken.value}.\n${USAGE}`);
      }
      if (flag === '--width') width = parsed;
      else height = parsed;
      continue;
    }
    if (arg.startsWith('--')) throw new Error(`Unknown option ${arg}.\n${USAGE}`);
    positional.push(arg);
  }

  if (positional.length !== 2) throw new Error(USAGE);

  const [url, outPath] = positional;
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    throw new Error(`Not a valid URL: ${url}\n${USAGE}`);
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    throw new Error(`URL must be http or https. Got ${url}\n${USAGE}`);
  }

  return { url, outPath, width, height, fullPage };
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const chrome = await findChrome();
  console.log(`Using Chrome: ${chrome.path}`);
  console.log(`Found via: ${chrome.via}`);

  mkdirSync(dirname(resolve(options.outPath)), { recursive: true });

  const browser = await puppeteer.launch({
    executablePath: chrome.path,
    headless: true,
    // Containers and cloud agents cannot use the Chrome sandbox or a large /dev/shm.
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
    defaultViewport: {
      width: options.width,
      height: options.height,
      deviceScaleFactor: 1,
    },
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({
      width: options.width,
      height: options.height,
      deviceScaleFactor: 1,
    });
    await page.goto(options.url, { waitUntil: 'networkidle0', timeout: 60_000 });
    await page.screenshot({
      path: options.outPath,
      type: 'png',
      fullPage: options.fullPage,
    });
  } finally {
    await browser.close();
  }

  const size = options.fullPage ? 'full page' : `${options.width}x${options.height}`;
  console.log(`Wrote ${resolve(options.outPath)} (${size})`);
}

main()
  .then(() => {
    process.exit(0);
  })
  .catch((error) => {
    console.error(error instanceof Error ? error.message : String(error));
    process.exit(1);
  });
