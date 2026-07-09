import { SimpleSectionItemDialog } from "./SimpleSectionItemDialog";

interface InterestsDialogProps {
  onClose: () => void;
  sectionId?: "interests";
  itemId: string;
}

export function InterestsDialog({
  onClose,
  itemId,
}: InterestsDialogProps): JSX.Element {
  return (
    <SimpleSectionItemDialog
      onClose={onClose}
      sectionId="interests"
      itemId={itemId}
    />
  );
}

export default InterestsDialog;
