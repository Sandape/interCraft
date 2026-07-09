import { SimpleSectionItemDialog } from "./SimpleSectionItemDialog";

interface PublicationsDialogProps {
  onClose: () => void;
  sectionId?: "publications";
  itemId: string;
}

export function PublicationsDialog({
  onClose,
  itemId,
}: PublicationsDialogProps): JSX.Element {
  return (
    <SimpleSectionItemDialog
      onClose={onClose}
      sectionId="publications"
      itemId={itemId}
    />
  );
}

export default PublicationsDialog;
