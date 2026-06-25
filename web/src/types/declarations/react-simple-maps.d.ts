declare module "react-simple-maps" {
  import { ComponentType, ReactElement, ReactNode, SVGProps } from "react";

  interface GeographiesChildren {
    geographies: GeographyType[];
  }

  interface GeographyType {
    rsmKey: string;
    properties: {
      name: string;
      [key: string]: string | number | undefined;
    };
    id: string;
    type: "Polygon" | "MultiPolygon";
    geometry: {
      type: string;
      coordinates: number[][][][] | number[][][];
    };
  }

  interface ComposableMapProps {
    projection?: string;
    projectionConfig?: {
      scale?: number;
      center?: [number, number];
      rotate?: [number, number, number];
    };
    width?: number;
    height?: number;
    style?: React.CSSProperties;
    children?: ReactNode;
  }

  interface GeographiesProps {
    geography: string | object;
    children: (data: GeographiesChildren) => ReactNode;
  }

  interface GeographyProps extends SVGProps<SVGPathElement> {
    geography: GeographyType;
    fill?: string;
    stroke?: string;
    strokeWidth?: number;
    style?: {
      default?: { outline?: string; fill?: string };
      hover?: { outline?: string; fill?: string };
      pressed?: { outline?: string; fill?: string };
    };
    onMouseEnter?: (event: React.MouseEvent) => void;
    onMouseMove?: (event: React.MouseEvent) => void;
    onMouseLeave?: (event: React.MouseEvent) => void;
  }

  interface SphereProps {
    stroke?: string;
    strokeWidth?: number;
    fill?: string;
  }

  interface GraticuleProps {
    stroke?: string;
    strokeWidth?: number;
  }

  export const ComposableMap: ComponentType<ComposableMapProps>;
  export const Geographies: ComponentType<GeographiesProps>;
  export const Geography: ComponentType<GeographyProps>;
  export const Sphere: ComponentType<SphereProps>;
  export const Graticule: ComponentType<GraticuleProps>;
  export const Marker: ComponentType<any>;
  export const ZoomableGroup: ComponentType<any>;
}
