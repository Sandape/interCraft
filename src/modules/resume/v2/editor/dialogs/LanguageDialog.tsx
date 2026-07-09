import { SimpleSectionItemDialog } from "./SimpleSectionItemDialog";

interface LanguageDialogProps {
  onClose: () => void;
  sectionId?: "languages";
  itemId: string;
}

export function LanguageDialog({
  onClose,
  itemId,
}: LanguageDialogProps): JSX.Element {
  return (
    <SimpleSectionItemDialog
      onClose={onClose}
      sectionId="languages"
      itemId={itemId}
    />
  );
}

export default LanguageDialog;
