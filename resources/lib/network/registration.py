form = """
<!DOCTYPE html>
<html>
	<head>
		<meta name="viewport" content="width=device-width, initial-scale=1">
		<title>Registration Form</title>
		<style>
			.container {
			position: absolute;
			top: 50%;
			left: 50%;
			transform: translate(-50%, -50%);
			-moz-transform: translate(-50%, -50%);
			-ms-transform: translate(-50%, -50%);
			-o-transform: translate(-50%, -50%);
			-webkit-transform: translate(-50%, -50%);
			border: 1px solid black;
			height: 200px;
			width: 300px;
			background-color: #0F0F0F;
			box-shadow: 5px 10px;
			}
			.inner {
			position: absolute;
			top: 50%;
			left: 50%;
			transform: translate(-50%, -50%);
			-moz-transform: translate(-50%, -50%);
			-ms-transform: translate(-50%, -50%);
			-o-transform: translate(-50%, -50%);
			-webkit-transform: translate(-50%, -50%);
			}
			.input {
			width: 200px;
			height: 26px;
			border: 0.6px solid black;
			background-color: #2E2E2E;
			color: white;
			}
			.button {
			width: 200px;
			height: 26px;
			border: 0.6px solid black;
			background-color: #1a1a1a;
			margin-top: 21px;
			cursor: pointer;
			color: white;
			}
			body {
			background-color: #0d0d0d;
			}
		</style>
	</head>
	<body>
		<div class="container">
			<form action="/register" method="post">
				<div class="inner">
					<input class="input" type="text" name="account" placeholder="Acount Name">
					<br/>
					<br/>
					<input class="input" type="text" name="client_id" placeholder="Client ID">
					<br/>
					<br/>
					<input class="input" type="text" name="client_secret" placeholder="Client Secret">
					<br/>
					<input class="button" type="submit" value="Submit">
				</div>
			</form>
		</div>
	</body>
</html>
"""

def status(output):
	return """
<!DOCTYPE html>
<html>
	<head>
		<meta name="viewport" content="width=device-width, initial-scale=1">
		<title>Registration Status</title>
		<style>
			body {
				background-color: #0d0d0d;
			}
			.container {
				position: absolute;
				top: 50%%;
				left: 50%%;
				transform: translate(-50%%, -50%%);
				-moz-transform: translate(-50%%, -50%%);
				-ms-transform: translate(-50%%, -50%%);
				-o-transform: translate(-50%%, -50%%);
				-webkit-transform: translate(-50%%, -50%%);
				border: 1px solid black;
				height: 200px;
				width: 300px;
				background-color: #0F0F0F;
				box-shadow: 5px 10px;
			}
			.inner {
				position: absolute;
				top: 50%%;
				left: 50%%;
				transform: translate(-50%%, -50%%);
				-moz-transform: translate(-50%%, -50%%);
				-ms-transform: translate(-50%%, -50%%);
				-o-transform: translate(-50%%, -50%%);
				-webkit-transform: translate(-50%%, -50%%);
				white-space: nowrap;
				overflow: hidden;
			}
			p {
				color: white;
				font-family: Arial, sans-serif;
				font-size: 13px;
				margin: 0;
				padding: 10px;
			}
		</style>
	</head>
	<body>
		<div class="container">
			<div class="inner">
				<p>%s</p>
			</div>
		</div>
	</body>
</html>
""" % (output)
