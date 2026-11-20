// Execute only the calculation functions from the pinned official browser asset.
// No DOM, network, filesystem or application code is exposed to the VM context.
import vm from 'node:vm';
import { createHash } from 'node:crypto';

const EXPECTED_SHA256 = 'f08c70ba2c5711d89c7a21644ec37830c9578df35085d13d1cfb2a6c4607c1e9';

export function runOfficial(source, inputs) {
  const actual = createHash('sha256').update(source).digest('hex');
  if (actual !== EXPECTED_SHA256) throw new Error('Official asset changed: review extraction boundaries again');
  const take = (start, end) => {
    const a = source.indexOf(start);
    const b = source.indexOf(end, a);
    if (a < 0 || b < 0) throw new Error('Official function boundary missing');
    return source.slice(a, b);
  };
  const constants = take('Qe=[', ',Cs=e=>');
  const slabFunctions = take('Cs=e=>', ',vn=()=>');
  const componentCalculations = take('se=(c,h,b,E,Q,O)=>', ',Et=()=>');
  const code = `
    const ${constants};
    const ${slabFunctions};
    function calculateOfficial(input) {
      let result = {};
      const p=input.assessment_year, g='Individual',
        M=input.resident ? 'Resident ' : 'Non-Resident',
        N=input.age<60 ? 'Less than 60 years' : input.age<80 ? 'Equal to 60 years or more but less than 80 years' : 'Equal to 80 years or more',
        Y=String(input.net_taxable_income),
        Z={E1:input.regime==='old'?'Yes':'No',E2:'Yes'},
        q={E3:false,E4:false,E5:false,E6:false,E7:false,E8:false},
        f=true,
        we=callback=>{result=callback(result)},
        d=()=>{}, setTimeout=()=>{};
      const ${componentCalculations};
      Xe();
      return result;
    }
    JSON.stringify(inputs.map(calculateOfficial));
  `;
  const context = vm.createContext({ inputs, console: {log() {}} });
  return { official_asset_sha256: actual, inputs_sha256: createHash('sha256').update(JSON.stringify(inputs)).digest('hex'), extraction: {constants: constants.length, slab_functions: slabFunctions.length, component_calculations: componentCalculations.length}, outputs: JSON.parse(new vm.Script(code).runInContext(context, {timeout:5000})) };
}
