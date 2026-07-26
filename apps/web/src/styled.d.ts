import "styled-components";
import type { AppTheme } from "./theme";

declare module "styled-components" {
  // Provides theme typing for styled-components props.
  export interface DefaultTheme extends AppTheme {}
}
