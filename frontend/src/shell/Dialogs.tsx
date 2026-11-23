/* Every dialog of the Recordings area that opens from the ui state, in one place (moved out of App.tsx).
   Each one's code loads on demand (lazyPreload) and is mounted only while its state says it is open. */
import { Suspense } from "react";
import { lazyPreload } from "../lazyPreload";
import { useApp } from "../store";

const ImportDialog = lazyPreload(() => import("../components/ImportDialog"));
const Help = lazyPreload(() => import("../components/Help"));
const GuideDialog = lazyPreload(() => import("../components/GuideDialog"));
const SettingsDialog = lazyPreload(() => import("../components/SettingsDialog"));
const CompareTable = lazyPreload(() => import("../components/CompareTable"));
const TemplateLibrary = lazyPreload(() => import("../components/TemplateLibrary"));
const ObjectDialog = lazyPreload(() => import("../components/ObjectDialog"));
const CompareObjectsDialog = lazyPreload(() => import("../components/CompareObjectsDialog"));
const PlaceDialog = lazyPreload(() => import("../components/PlaceDialog"));
const CompareSimilarDialog = lazyPreload(() => import("../components/CompareSimilarDialog"));
const PlaceOnMapDialog = lazyPreload(() => import("../components/PlaceOnMapDialog"));
const SyncDialog = lazyPreload(() => import("../components/SyncDialog"));
const TransformDialog = lazyPreload(() => import("../components/TransformDialog"));
const RetargetDialog = lazyPreload(() => import("../components/RetargetDialog"));
const SameWorkDialog = lazyPreload(() => import("../components/SameWorkDialog"));
const TimeAxisDialog = lazyPreload(() => import("../components/TimeAxisDialog"));
const StyleLinesDialog = lazyPreload(() => import("../components/StyleLinesDialog"));
const ExportRecordingDialog = lazyPreload(() => import("../components/ExportRecordingDialog"));
const QualityDialog = lazyPreload(() => import("../components/QualityDialog"));
const RunsMatrix = lazyPreload(() => import("../components/RunsMatrix"));

export default function Dialogs() {
  const importPaths = useApp((s) => s.importPaths);
  const helpOpen = useApp((s) => s.helpOpen);
  const guideOpen = useApp((s) => s.guideOpen);
  const settingsOpen = useApp((s) => s.settingsOpen);
  const compareTable = useApp((s) => !!s.compareTable);
  const templatesOpen = useApp((s) => s.templatesOpen);
  const objectDialog = useApp((s) => s.objectDialog);
  const compareDialog = useApp((s) => s.compareDialog);
  const placeEdit = useApp((s) => s.placeEdit);
  const similarDialog = useApp((s) => s.similarDialog);
  const placeDialog = useApp((s) => s.placeDialog);
  const syncFor = useApp((s) => s.syncFor);
  const transformOpen = useApp((s) => !!s.transformTargets);
  const retargetOpen = useApp((s) => !!s.retarget);
  const sameWorkOpen = useApp((s) => !!s.sameWorkFor);
  const timeAxisOpen = useApp((s) => !!s.timeAxisFor);
  const styleOpen = useApp((s) => !!s.styleDialog);
  const exportRecOpen = useApp((s) => s.exportRecOpen);
  const qualityOpen = useApp((s) => !!s.qualityFor);
  const matrixOpen = useApp((s) => s.matrixOpen);
  return (
    <Suspense fallback={null}>
      {importPaths && <ImportDialog />}
      {helpOpen && <Help />}
      {guideOpen && <GuideDialog />}
      {settingsOpen && <SettingsDialog />}
      {compareTable && <CompareTable />}
      {templatesOpen && <TemplateLibrary />}
      {objectDialog && <ObjectDialog key={`${objectDialog.plotId}/${objectDialog.objectId ?? "new"}`} />}
      {compareDialog && <CompareObjectsDialog key={compareDialog.plotId} />}
      {placeEdit && <PlaceDialog key={placeEdit.id ?? "new"} />}
      {similarDialog && <CompareSimilarDialog key={`${similarDialog.runId}/${similarDialog.ids.join(",")}`} />}
      {placeDialog && <PlaceOnMapDialog key={placeDialog} />}
      {syncFor && <SyncDialog />}
      {transformOpen && <TransformDialog />}
      {retargetOpen && <RetargetDialog />}
      {sameWorkOpen && <SameWorkDialog />}
      {timeAxisOpen && <TimeAxisDialog />}
      {styleOpen && <StyleLinesDialog />}
      {exportRecOpen && <ExportRecordingDialog />}
      {qualityOpen && <QualityDialog />}
      {matrixOpen && <RunsMatrix />}
    </Suspense>
  );
}
