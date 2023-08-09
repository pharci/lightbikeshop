function getToken(name) {
	var cookieValue = null;
	if (document.cookie && document.cookie !== '') {
		var cookies = document.cookie.split(';');
		for (var i = 0; i < cookies.length; i++) {
		    var cookie = cookies[i].trim();
		    // Does this cookie string begin with the name we want?
		    if (cookie.substring(0, name.length + 1) === (name + '=')) {
		        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
		        break;
		    }
		}
	}
	return cookieValue;
}

function getCookie(name) {
	// Split cookie string and get all individual name=value pairs in an array
	var cookieArr = document.cookie.split(";");

	// Loop through the array elements
	for(var i = 0; i < cookieArr.length; i++) {
		var cookiePair = cookieArr[i].split("=");

		/* Removing whitespace at the beginning of the cookie name
		and compare it with the given string */
		if(name == cookiePair[0].trim()) {
		    // Decode the cookie value and return
		    return decodeURIComponent(cookiePair[1]);
		}
	}

	// Return null if not found
	return null;
}
var cookies_cart = JSON.parse(getCookie('cookies_cart'))

if (cookies_cart == undefined){
	cookies_cart = {}
	document.cookie ='cookies_cart=' + JSON.stringify(cookies_cart) + ";domain=;path=/"
}