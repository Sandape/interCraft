/**
 * Register page — deep-link to the auth form in register mode.
 * Reuses the Login component with `initialMode="register"`.
 */
import Login from './Login'

export default function Register() {
  return <Login initialMode="register" />
}
