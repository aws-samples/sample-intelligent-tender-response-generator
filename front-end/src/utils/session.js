export async function signOutRedirect(auth) {
    await auth.removeUser()
    const logoutUri = `${window.location.origin}/login`;

    window.location.href = `${process.env.REACT_APP_COGNITO_DOMAIN}/logout?client_id=${process.env.REACT_APP_USER_POOL_CLIENT_ID}&logout_uri=${encodeURIComponent(logoutUri)}`;
}