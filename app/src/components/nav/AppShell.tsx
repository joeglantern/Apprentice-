/** The persistent navigation chrome: a 68px icon rail on desktop, a 64px bottom bar
 * on phone, and nothing at all on auth and onboarding.
 *
 * It wraps the router's Stack rather than being a Tabs navigator. The rail carries
 * a logo header, a settings item split to the bottom, and an avatar with a presence
 * dot - none of which a tab bar can express - and canvas detail keeps the chrome
 * while being a pushed route, which a tab group would not allow. */

import { usePathname, useRouter } from "expo-router";
import { StyleSheet, View, type ViewStyle } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useJobHistory } from "@/hooks/useJobHistory";
import { radii, type } from "@/lib/tokens";
import { useTheme } from "@/theme/theme";

import { Icon, type IconName } from "../ui/Icon";
import { Mono } from "../ui/type";
import { Pulse } from "../ui/Pulse";
import { PressScale } from "../ui/press";
import { UmbraMark } from "../ui/marks";

interface Dest {
  href: string;
  label: string;
  icon: IconName;
}

const RAIL: Dest[] = [
  { href: "/", label: "explore", icon: "compass" },
  { href: "/create", label: "create", icon: "plusSquare" },
  { href: "/chat", label: "chat", icon: "chat" },
  { href: "/kits", label: "brand kits", icon: "swatches" },
  { href: "/jobs", label: "jobs", icon: "list" },
];

/** Brand kits is reachable from create and the rail, so the phone bar stays at five. */
const TABS: Dest[] = [
  { href: "/", label: "explore", icon: "compass" },
  { href: "/create", label: "create", icon: "plusSquare" },
  { href: "/chat", label: "chat", icon: "chat" },
  { href: "/jobs", label: "jobs", icon: "list" },
  { href: "/settings", label: "settings", icon: "sliders" },
];

const SETTINGS: Dest = { href: "/settings", label: "settings", icon: "sliders" };

const CHROMELESS = ["/auth", "/onboarding"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { c, isDesktop } = useTheme();
  const pathname = usePathname();

  if (CHROMELESS.includes(pathname)) return <>{children}</>;

  return (
    <View style={[styles.root, { backgroundColor: c.bg0, flexDirection: isDesktop ? "row" : "column" }]}>
      {isDesktop ? <Rail pathname={pathname} /> : null}
      <View style={styles.content}>{children}</View>
      {isDesktop ? null : <TabBar pathname={pathname} />}
    </View>
  );
}

/** Canvas detail is opened from explore, so explore stays lit while you are in it. */
function isActive(pathname: string, href: string) {
  const here = pathname === "/canvas" ? "/" : pathname;
  return here === href;
}

/** Move between destinations without stacking them up.
 *
 * `navigate` returns to a route already in the navigation state instead of pushing a
 * duplicate, so the stack stays bounded by the number of destinations and the web
 * back button walks them rather than replaying a hall of mirrors. Pushing also
 * remounted the screen every time, which is why chat used to start a new thread on
 * every visit. Detail routes like /canvas still push, because back should return to
 * the list you opened them from. */
function useGoTo(pathname: string) {
  const router = useRouter();
  return (href: string) => {
    if (isActive(pathname, href)) return;
    router.navigate(href as never);
  };
}

function useAnythingRunning() {
  const { data } = useJobHistory();
  return !!data?.some((j) => j.status !== "done" && j.status !== "error");
}

function Rail({ pathname }: { pathname: string }) {
  const { c } = useTheme();
  const goTo = useGoTo(pathname);
  const insets = useSafeAreaInsets();
  const running = useAnythingRunning();

  return (
    <View
      style={[
        styles.rail,
        { backgroundColor: c.void, paddingTop: 16 + insets.top, paddingBottom: 14 + insets.bottom },
      ]}
    >
      <View style={styles.railLogo}>
        <UmbraMark size={36} color={c.t1} />
      </View>

      {RAIL.map((d) => (
        <RailItem
          key={d.href}
          dest={d}
          active={isActive(pathname, d.href)}
          badge={d.href === "/jobs" && running}
          onPress={() => goTo(d.href)}
        />
      ))}

      <View style={styles.railFoot}>
        <RailItem
          dest={SETTINGS}
          active={isActive(pathname, SETTINGS.href)}
          onPress={() => goTo(SETTINGS.href)}
        />
        <View style={[styles.avatar, { backgroundColor: c.raise }]}>
          <Mono size={9} color={c.t2}>
            LB
          </Mono>
          <View style={[styles.presence, { backgroundColor: c.success, borderColor: c.void }]} />
        </View>
      </View>
    </View>
  );
}

function RailItem({
  dest,
  active,
  badge,
  onPress,
}: {
  dest: Dest;
  active: boolean;
  badge?: boolean;
  onPress: () => void;
}) {
  const { c } = useTheme();
  return (
    <PressScale
      scale={0.92}
      onPress={onPress}
      accessibilityRole="link"
      accessibilityLabel={dest.label}
      accessibilityState={{ selected: active }}
      style={[styles.railItem, active && { backgroundColor: c.raise }] as ViewStyle[]}
    >
      <Icon name={dest.icon} size={20} color={c.t1} opacity={active ? 1 : 0.48} />
      {badge ? (
        <Pulse style={[styles.badge, { backgroundColor: c.accent }]} durationMs={2000} />
      ) : null}
    </PressScale>
  );
}

function TabBar({ pathname }: { pathname: string }) {
  const { c } = useTheme();
  const goTo = useGoTo(pathname);
  const insets = useSafeAreaInsets();

  return (
    <View
      style={[
        styles.tabBar,
        { backgroundColor: c.bg0, borderTopColor: c.ln, paddingBottom: insets.bottom },
      ]}
    >
      {TABS.map((d) => {
        const active = isActive(pathname, d.href);
        return (
          <PressScale
            key={d.href}
            scale={0.94}
            onPress={() => goTo(d.href)}
            accessibilityRole="link"
            accessibilityLabel={d.label}
            accessibilityState={{ selected: active }}
            style={styles.tab}
          >
            <Icon name={d.icon} size={19} color={c.t1} opacity={active ? 1 : 0.48} />
            <Mono size={type.monoXS} weight="500" color={active ? c.t1 : c.t3} style={styles.tabLabel}>
              {d.label}
            </Mono>
          </PressScale>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  content: { flex: 1, minWidth: 0 },

  rail: { width: 68, flexShrink: 0, alignItems: "center", gap: 5 },
  railLogo: { marginBottom: 16 },
  railItem: {
    width: 46,
    height: 46,
    borderRadius: radii.navItem,
    alignItems: "center",
    justifyContent: "center",
  },
  railFoot: { marginTop: "auto", alignItems: "center", gap: 10 },
  badge: { position: "absolute", top: 8, right: 8, width: 5, height: 5, borderRadius: 2.5 },
  avatar: { width: 30, height: 30, borderRadius: 15, alignItems: "center", justifyContent: "center" },
  presence: {
    position: "absolute",
    bottom: -1,
    right: -1,
    width: 8,
    height: 8,
    borderRadius: 4,
    borderWidth: 2,
  },

  tabBar: { flexDirection: "row", borderTopWidth: StyleSheet.hairlineWidth },
  tab: { flex: 1, height: 64, alignItems: "center", justifyContent: "center", gap: 4 },
  tabLabel: { letterSpacing: 0 },
});
