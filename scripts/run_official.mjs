// Optional independent re-execution when Node is installed: node scripts/run_official.mjs
import fs from 'node:fs/promises';
import { runOfficial } from './official_calculator.mjs';

const root = new URL('../', import.meta.url);
const path = name => new URL('data/official_calculator/'+name, root);
const source = await fs.readFile(path('calculator.js'), 'utf8');
const inputs = JSON.parse(await fs.readFile(path('check_inputs.json'), 'utf8'));
const result = runOfficial(source, inputs);
await fs.writeFile(path('check_outputs.json'), JSON.stringify({...result, execution:'Downloaded official calculator functions executed in isolated Node VM; not manual browser observations'}, null, 2)+'\n');
console.log(`Recorded ${result.outputs.length} actual official-asset calculations`);
