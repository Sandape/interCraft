// Lightweight TemplateProvider — passes the data + styles to primitives
// that need them via context. Templates call useTemplate() when they
// need access to `data` or computed styles inside helper components.
//
// For T032 we expose a minimal shape — a more elaborate context (carrying
// computed `styles` like reactive-resume's TemplateProvider) is added in
// US4/US8 when style rules land.

import { createContext, useContext, type ReactNode } from "react";
import type { ResumeDataV2 } from "../../schema/data";

export interface TemplateContextValue {
  data?: ResumeDataV2;
}

const TemplateContext = createContext<TemplateContextValue>({});

export interface TemplateProviderProps {
  value: TemplateContextValue;
  children: ReactNode;
}

export const TemplateProvider = ({ value, children }: TemplateProviderProps) => (
  <TemplateContext.Provider value={value}>{children}</TemplateContext.Provider>
);

export const useTemplate = (): TemplateContextValue => useContext(TemplateContext);
