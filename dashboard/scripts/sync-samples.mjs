// 레포 맨 위 samples/*.json(CLI 담당이 관리)을 대시보드 mock 데이터 한 파일로 합친다.
// dashboard/ 안에서만 빌드되므로(Docker 포함) 바깥 폴더를 직접 import 하지 않고 복사해 둔다.
// 샘플이 바뀌면: cd dashboard && npm run samples:sync
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, "..", "..", "samples");
const out = join(here, "..", "lib", "data", "mock", "sample-events.json");

const events = readdirSync(src)
  .filter((f) => f.endsWith(".json"))
  .sort()
  .map((f) => JSON.parse(readFileSync(join(src, f), "utf8")));

writeFileSync(out, JSON.stringify(events, null, 2) + "\n");
console.log(`samples ${events.length}건 → ${out}`);
