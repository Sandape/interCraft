import { SimpleSectionItemDialog } from "./SimpleSectionItemDialog";

interface ReferencesDialogProps {
  onClose: () => void;
  sectionId?: "references";
  itemId: string;
}

export function ReferencesDialog({
  onClose,
  itemId,
}: ReferencesDialogProps): JSX.Element {
  return (
    <SimpleSectionItemDialog
      onClose={onClose}
      sectionId="references"
      itemId={itemId}
    />
  );
}

export default ReferencesDialog;
