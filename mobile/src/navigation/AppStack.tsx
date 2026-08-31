import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import { Pressable } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import HomeScreen from '../screens/marketplace/HomeScreen';
import SearchScreen from '../screens/marketplace/SearchScreen';
import ChatScreen from '../screens/chat/ConversationListScreen';
import ProfileScreen from '../screens/profile/ProfileScreen';
import AdminScreen from '../screens/admin/AdminScreen';
import MyListingsScreen from '../screens/selling/MyListingsScreen';
import { useAuth } from '../context/AuthContext';
import { colors } from '../theme';
import type { AppTabParamList, RootStackParamList } from './types';

const Tab = createBottomTabNavigator<AppTabParamList>();

function CartHeaderButton() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="View cart"
      onPress={() => navigation.navigate('Cart')}
      hitSlop={8}
      style={({ pressed }) => ({ opacity: pressed ? 0.6 : 1, marginRight: 8 })}
    >
      <Ionicons name="cart-outline" size={24} color={colors.text} />
    </Pressable>
  );
}

function AddListingHeaderButton() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="Add listing"
      onPress={() => navigation.navigate('AddProduct')}
      hitSlop={8}
      style={({ pressed }) => ({ opacity: pressed ? 0.6 : 1, marginRight: 8 })}
    >
      <Ionicons name="add-circle-outline" size={26} color={colors.primary} />
    </Pressable>
  );
}

const ICONS: Record<
  keyof AppTabParamList,
  { active: keyof typeof Ionicons.glyphMap; inactive: keyof typeof Ionicons.glyphMap }
> = {
  Home: { active: 'home', inactive: 'home-outline' },
  Search: { active: 'search', inactive: 'search-outline' },
  Selling: { active: 'pricetag', inactive: 'pricetag-outline' },
  Chat: { active: 'chatbubbles', inactive: 'chatbubbles-outline' },
  Profile: { active: 'person', inactive: 'person-outline' },
  Admin: { active: 'shield-checkmark', inactive: 'shield-checkmark-outline' },
};

export default function AppStack() {
  const { user } = useAuth();
  const email = user?.email?.toLowerCase() ?? '';
  const isAdmin = user?.is_staff || user?.profile?.role === 'ADMIN' || email === 'admin@gmail.com';
  const isSeller = user?.profile?.role === 'SELLER' || email === 'lidyakimomwe@gmail.com' || email.includes('seller');

  // Determine initial landing tab based on user role
  const initialRouteName: keyof AppTabParamList = isAdmin
    ? 'Admin'
    : isSeller
      ? 'Selling'
      : 'Home';

  return (
    <Tab.Navigator
      id={undefined}
      initialRouteName={initialRouteName}
      screenOptions={({ route }) => ({
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textSecondary,
        headerShadowVisible: false,
        headerStyle: { backgroundColor: colors.background },
        headerTintColor: colors.text,
        tabBarIcon: ({ focused, color, size }) => (
          <Ionicons
            name={focused ? ICONS[route.name].active : ICONS[route.name].inactive}
            size={size}
            color={color}
          />
        ),
      })}
    >
      <Tab.Screen
        name="Home"
        component={HomeScreen}
        options={{ title: 'ReuseHub', headerRight: () => <CartHeaderButton /> }}
      />
      <Tab.Screen name="Search" component={SearchScreen} options={{ title: 'Search' }} />
      <Tab.Screen
        name="Selling"
        component={MyListingsScreen}
        options={{
          title: 'Selling',
          headerRight: () => <AddListingHeaderButton />,
        }}
      />
      <Tab.Screen name="Chat" component={ChatScreen} options={{ title: 'Chat' }} />
      <Tab.Screen name="Profile" component={ProfileScreen} options={{ title: 'Profile' }} />
      {isAdmin ? (
        <Tab.Screen name="Admin" component={AdminScreen} options={{ title: 'Admin' }} />
      ) : null}
    </Tab.Navigator>
  );
}
