/** The persistent navigation chrome: an icon rail on desktop that expands to show
 * labels and your sessions, a 64px bottom bar on phone, and nothing at all on auth
 * and onboarding.
 *
 * It wraps the router's Stack rather than being a Tabs navigator. The rail carries
 * a logo header, a settings item split to the bottom, and an avatar with a presence
 * dot - none of which a tab bar can express - and canvas detail keeps the chrome
 * while being a pushed route, which a tab group would not allow. */

import { usePathname, useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { Animated, Easing, StyleSheet, View, type ViewStyle } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useJobHistory } from "@/hooks/useJobHistory";
import { radii, type } from "@/lib/tokens";
import { useSession } from "@/state/session";
import { useTheme } from "@/theme/theme";

import { Icon, type IconName } from "../ui/Icon";
import { Body, Mono } from "../ui/type";
import { Pulse } from "../ui/Pulse";
import { PressScale } from "../ui/press";
import { UmbraMark } from "../ui/marks";
import { SessionList } from "./SessionList";

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

const RAIL_COLLAPSED = 68;
const RAIL_EXPANDED = 232;
/** Below this an expanded rail eats a fifth of the window, so it starts collapsed
 * unless someone has said otherwise. */
const ROOMY = 1280;

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
  const { c, width } = useTheme();
  const goTo = useGoTo(pathname);
  const insets = useSafeAreaInsets();
  const running = useAnythingRunning();
  const { railExpanded, setRailExpanded, threadId, setThreadId, newSession } = useSession();

  // No stated preference means decide from the window: roomy screens get labels.
  const expanded = railExpanded ?? width >= ROOMY;
  const [open] = useState(() => new Animated.Value(expanded ? 1 : 0));

  useEffect(() => {
    // The one animation here that cannot use the native driver, because width is not
    // a transform. Acceptable because it only ever runs on desktop, on a single view,
    // beside a flex child that reflows cheaply. Do not "fix" this to useNativeDriver;
    // it will silently stop animating.
    const anim = Animated.timing(open, {
      toValue: expanded ? 1 : 0,
      duration: 180,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: false,
    });
    anim.start();
    return () => anim.stop();
  }, [expanded, open]);

  const railWidth = open.interpolate({
    inputRange: [0, 1],
    outputRange: [RAIL_COLLAPSED, RAIL_EXPANDED],
  });

  return (
    <Animated.View
      style={[
        styles.rail,
        expanded ? styles.railWide : styles.railNarrow,
        {
          width: railWidth,
          backgroundColor: c.void,
          paddingTop: 16 + insets.top,
          paddingBottom: 14 + insets.bottom,
        },
      ]}
    >
      <View style={[styles.railHead, expanded && styles.railHeadWide]}>
        <UmbraMark size={36} color={c.t1} />
        <PressScale
          scale={0.9}
          onPress={() => setRailExpanded(!expanded)}
          accessibilityRole="button"
          accessibilityLabel={expanded ? "collapse sidebar" : "expand sidebar"}
          style={styles.toggle}
        >
          <Animated.View
            style={{
              transform: [
                {
                  rotate: open.interpolate({ inputRange: [0, 1], outputRange: ["180deg", "0deg"] }),
                },
              ],
            }}
          >
            <Icon name="arrowLeft" size={16} color={c.t3} />
          </Animated.View>
        </PressScale>
      </View>

      {RAIL.map((d) => (
        <RailItem
          key={d.href}
          dest={d}
          expanded={expanded}
          labelOpacity={open}
          active={isActive(pathname, d.href)}
          badge={d.href === "/jobs" && running}
          onPress={() => goTo(d.href)}
        />
      ))}

      {expanded ? (
        <View style={styles.sessions}>
          <SessionList
            activeId={threadId}
            onOpen={(id) => {
              setThreadId(id);
              goTo("/chat");
            }}
            onNew={() => {
              newSession();
              goTo("/create");
            }}
          />
        </View>
      ) : null}

      <View style={[styles.railFoot, expanded && styles.railFootWide]}>
        <RailItem
          dest={SETTINGS}
          expanded={expanded}
          labelOpacity={open}
          active={isActive(pathname, SETTINGS.href)}
          onPress={() => goTo(SETTINGS.href)}
        />
        <View style={[styles.avatarRow, expanded && styles.avatarRowWide]}>
          <View style={[styles.avatar, { backgroundColor: c.raise }]}>
            <Mono size={9} color={c.t2}>
              LB
            </Mono>
            <View style={[styles.presence, { backgroundColor: c.success, borderColor: c.void }]} />
          </View>
          {expanded ? (
            <Animated.View style={{ opacity: open }}>
              <Mono size={type.monoXS} color={c.t3} numberOfLines={1}>
                liban
              </Mono>
            </Animated.View>
          ) : null}
        </View>
      </View>
    </Animated.View>
  );
}

function RailItem({
  dest,
  active,
  badge,
  expanded,
  labelOpacity,
  onPress,
}: {
  dest: Dest;
  active: boolean;
  badge?: boolean;
  expanded: boolean;
  labelOpacity: Animated.Value;
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
      style={
        [
          styles.railItem,
          expanded ? styles.railItemWide : styles.railItemNarrow,
          active && { backgroundColor: c.raise },
        ] as ViewStyle[]
      }
    >
      <View style={styles.railIcon}>
        <Icon name={dest.icon} size={20} color={c.t1} opacity={active ? 1 : 0.48} />
        {badge && !expanded ? (
          <Pulse style={[styles.badge, { backgroundColor: c.accent }]} durationMs={2000} />
        ) : null}
      </View>
      {expanded ? (
        <Animated.View style={[styles.railLabel, { opacity: labelOpacity }]}>
          <Body size={type.bodyXS} color={active ? c.t1 : c.t2} numberOfLines={1}>
            {dest.label}
          </Body>
        </Animated.View>
      ) : null}
      {badge && expanded ? (
        <Pulse style={[styles.badgeInline, { backgroundColor: c.accent }]} durationMs={2000} />
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

  rail: { flexShrink: 0, gap: 5, overflow: "hidden" },
  railNarrow: { alignItems: "center" },
  railWide: { alignItems: "stretch", paddingHorizontal: 11 },

  railHead: { marginBottom: 16, alignItems: "center" },
  railHeadWide: { flexDirection: "row", justifyContent: "space-between", paddingHorizontal: 5 },
  toggle: { width: 28, height: 28, alignItems: "center", justifyContent: "center", borderRadius: 8 },

  railItem: { height: 46, borderRadius: radii.navItem, alignItems: "center" },
  railItemNarrow: { width: 46, justifyContent: "center" },
  railItemWide: { flexDirection: "row", paddingHorizontal: 13, gap: 12 },
  railIcon: { width: 20, height: 20, alignItems: "center", justifyContent: "center" },
  railLabel: { flex: 1, minWidth: 0 },

  sessions: { flex: 1, minHeight: 0, marginTop: 14 },

  railFoot: { marginTop: "auto", alignItems: "center", gap: 10, paddingTop: 10 },
  railFootWide: { alignItems: "stretch" },

  badge: { position: "absolute", top: -4, right: -4, width: 5, height: 5, borderRadius: 2.5 },
  badgeInline: { width: 5, height: 5, borderRadius: 2.5 },

  avatarRow: { alignItems: "center" },
  avatarRowWide: { flexDirection: "row", gap: 10, paddingHorizontal: 13 },
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
