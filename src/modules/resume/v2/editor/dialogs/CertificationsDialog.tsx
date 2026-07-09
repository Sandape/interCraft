import { SimpleSectionItemDialog } from "./SimpleSectionItemDialog";

interface CertificationsDialogProps {
  onClose: () => void;
  sectionId?: "certifications";
  itemId: string;
}

export function CertificationsDialog({
  onClose,
  itemId,
}: CertificationsDialogProps): JSX.Element {
  return (
    <SimpleSectionItemDialog
      onClose={onClose}
      sectionId="certifications"
      itemId={itemId}
    />
  );
}

export default CertificationsDialog;
