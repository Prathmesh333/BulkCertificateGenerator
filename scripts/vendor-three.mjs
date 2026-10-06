import {copyFile, mkdir} from 'node:fs/promises';
await mkdir('app/static/vendor', {recursive:true});
for (const name of ['three.module.js','three.core.js']) {
  await copyFile(`node_modules/three/build/${name}`, `app/static/vendor/${name}`);
}
await copyFile('node_modules/three/LICENSE', 'app/static/vendor/THREE-LICENSE.txt');
