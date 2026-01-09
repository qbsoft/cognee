import { NextResponse, type NextRequest } from "next/server";
// import { auth0 } from "./modules/auth/auth0";

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export async function middleware(request: NextRequest) {
  // if (process.env.USE_AUTH0_AUTHORIZATION?.toLowerCase() === "true") {
  //   if (request.nextUrl.pathname === "/auth/token") {
  //       return NextResponse.next();
  //   }

  //   const response: NextResponse = await auth0.middleware(request);

  //   return response;
  // }

  // Check authentication for protected routes
  const protectedRoutes = ['/dashboard', '/account', '/plan', '/(graph)', '/admin', '/tenant-admin'];
  const isProtectedRoute = protectedRoutes.some(route => 
    request.nextUrl.pathname.startsWith(route)
  );
  
  // If accessing protected route and not on auth pages
  if (isProtectedRoute && !request.nextUrl.pathname.startsWith('/auth')) {
    // Check if user has auth cookie
    const authCookie = request.cookies.get('auth_token');
    
    // If no auth cookie, redirect to login
    // Note: We only check cookie existence here. The actual validation
    // happens client-side through API calls to /api/v1/auth/me
    // which will trigger a redirect in handleServerErrors.ts if the cookie is invalid
    if (!authCookie) {
      const loginUrl = new URL('/auth/login', request.url);
      loginUrl.searchParams.set('redirect', request.nextUrl.pathname);
      return NextResponse.redirect(loginUrl);
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico, sitemap.xml, robots.txt (metadata files)
     */
    "/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)",
  ],
};
