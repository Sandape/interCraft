import { SimpleSectionItemDialog } from "./SimpleSectionItemDialog";

interface VolunteerDialogProps {
  onClose: () => void;
  sectionId?: "volunteer";
  itemId: string;
}

export function VolunteerDialog({
  onClose,
  itemId,
}: VolunteerDialogProps): JSX.Element {
  return (
    <SimpleSectionItemDialog
      onClose={onClose}
      sectionId="volunteer"
      itemId={itemId}
    />
  );
}

export default VolunteerDialog;
