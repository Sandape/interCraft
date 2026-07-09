import { SimpleSectionItemDialog } from "./SimpleSectionItemDialog";

interface AwardsDialogProps {
  onClose: () => void;
  sectionId?: "awards";
  itemId: string;
}

export function AwardsDialog({
  onClose,
  itemId,
}: AwardsDialogProps): JSX.Element {
  return (
    <SimpleSectionItemDialog onClose={onClose} sectionId="awards" itemId={itemId} />
  );
}

export default AwardsDialog;
