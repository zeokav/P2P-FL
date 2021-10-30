var path = require('path');

module.exports = {
  context: __dirname + "/app",
  entry: "./js/main.js",
  output: {
    filename: "./bundle.js"
  },
  module: {
    loaders: [
      {
        loader: 'babel-loader',
        include: [
          path.resolve(__dirname, "app/js"),
        ],
        test: /\.js$/,
        query: {
          presets: 'es2015'
        }
      }
    ]
  },
  devServer: {
    contentBase: "./app"
  },
  devtool: 'source-map'
};
